//! The few Windows calls std does not offer: for the diagnostic receipts, actual OS
//! process creation times, the OS build, and handle-relative file creation (NtCreateFile
//! with a RootDirectory), so a receipt write never walks a path that could be replaced;
//! and for Make, starting the one `tapectl make` child elevated (ShellExecuteExW "runas").
#![cfg(windows)]

use std::ffi::c_void;
use std::fs::File;
use std::io;
use std::os::windows::io::{AsRawHandle, FromRawHandle, RawHandle};

#[repr(C)]
struct FileTime { low: u32, high: u32 }
#[repr(C)]
struct OsVersionInfo { size: u32, major: u32, minor: u32, build: u32, platform: u32, csd: [u16; 128] }
#[repr(C)]
struct UnicodeString { length: u16, maximum: u16, buffer: *const u16 }
#[repr(C)]
struct ObjectAttributes { length: u32, root: RawHandle, name: *const UnicodeString, attributes: u32, security: *const c_void, qos: *const c_void }
#[repr(C)]
struct IoStatusBlock { status: usize, information: usize }

/// SHELLEXECUTEINFOW (shellapi.h), natural C layout.
#[repr(C)]
struct ShellExecuteInfo {
    size: u32, mask: u32, hwnd: isize, verb: *const u16, file: *const u16, params: *const u16, dir: *const u16,
    show: i32, inst_app: isize, id_list: *mut c_void, class: *const u16, hkey_class: isize, hotkey: u32,
    icon_or_monitor: isize, process: RawHandle,
}

#[link(name = "kernel32")]
extern "system" {
    fn GetProcessTimes(process: RawHandle, creation: *mut FileTime, exit: *mut FileTime, kernel: *mut FileTime, user: *mut FileTime) -> i32;
    fn GetCurrentProcess() -> RawHandle;
    fn WaitForSingleObject(handle: RawHandle, ms: u32) -> u32;
    fn GetExitCodeProcess(process: RawHandle, code: *mut u32) -> i32;
    fn CloseHandle(handle: RawHandle) -> i32;
    fn GetLastError() -> u32;
}
#[link(name = "shell32")]
extern "system" {
    fn ShellExecuteExW(info: *mut ShellExecuteInfo) -> i32;
}

const SEE_MASK_NOCLOSEPROCESS: u32 = 0x40;
const SEE_MASK_NOASYNC: u32 = 0x100;
const SEE_MASK_FLAG_NO_UI: u32 = 0x400;
const SW_HIDE: i32 = 0;
const ERROR_CANCELLED: u32 = 1223;
const WAIT_OBJECT_0: u32 = 0;

/// A started child process, closed on drop.
pub struct Process(RawHandle);
// SAFETY: a process handle may be waited on from any thread.
unsafe impl Send for Process {}
impl Process {
    /// Its exit code once it has exited, waiting at most `ms`.
    pub fn wait_ms(&self, ms: u32) -> Option<u32> {
        // SAFETY: a live process handle owned by self.
        if unsafe { WaitForSingleObject(self.0, ms) } != WAIT_OBJECT_0 { return None; }
        let mut code = 0u32;
        // SAFETY: as above, with a writable u32.
        (unsafe { GetExitCodeProcess(self.0, &mut code) } != 0).then_some(code)
    }
}
impl Drop for Process {
    fn drop(&mut self) {
        // SAFETY: closed exactly once.
        unsafe { CloseHandle(self.0) };
    }
}

pub enum Elevated { Declined, Failed(String), Started(Process) }

fn wide(s: &str) -> Vec<u16> { s.encode_utf16().chain(std::iter::once(0)).collect() }

/// Start `file` with `params` elevated ("runas": the UAC prompt), hidden, owned by `owner`.
/// A declined prompt is ERROR_CANCELLED and starts nothing.
pub fn runas(file: &std::path::Path, params: &str, dir: &std::path::Path, owner: isize) -> Elevated {
    let (verb, file, params, dir) = (wide("runas"), wide(&file.to_string_lossy()), wide(params), wide(&dir.to_string_lossy()));
    let mut info = ShellExecuteInfo { size: std::mem::size_of::<ShellExecuteInfo>() as u32,
        mask: SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC | SEE_MASK_FLAG_NO_UI, hwnd: owner, verb: verb.as_ptr(),
        file: file.as_ptr(), params: params.as_ptr(), dir: dir.as_ptr(), show: SW_HIDE, inst_app: 0,
        id_list: std::ptr::null_mut(), class: std::ptr::null(), hkey_class: 0, hotkey: 0, icon_or_monitor: 0,
        process: std::ptr::null_mut() };
    // SAFETY: every pointer refers to a live, NUL-terminated local for the duration of the call.
    if unsafe { ShellExecuteExW(&mut info) } == 0 {
        // SAFETY: no other call in between.
        let e = unsafe { GetLastError() };
        return if e == ERROR_CANCELLED { Elevated::Declined } else { Elevated::Failed(format!("ShellExecuteExW runas: Windows error {e}")) };
    }
    if info.process.is_null() { return Elevated::Failed("ShellExecuteExW returned no process".into()); }
    Elevated::Started(Process(info.process))
}
#[link(name = "ntdll")]
extern "system" {
    fn RtlGetVersion(info: *mut OsVersionInfo) -> i32;
    fn NtCreateFile(handle: *mut RawHandle, access: u32, attributes: *const ObjectAttributes, io: *mut IoStatusBlock,
        allocation: *const i64, file_attributes: u32, share: u32, disposition: u32, options: u32, ea: *const c_void, ea_length: u32) -> i32;
}

/// FILETIME epoch (1601) to Unix epoch, in 100 ns ticks.
const EPOCH_DELTA: u64 = 116_444_736_000_000_000;

/// The actual OS creation time of a process, as Unix nanoseconds.
pub fn process_start_ns(process: RawHandle) -> Option<u128> {
    let z = || FileTime { low: 0, high: 0 };
    let (mut c, mut e, mut k, mut u) = (z(), z(), z(), z());
    // SAFETY: a valid process handle and four writable FILETIMEs.
    if unsafe { GetProcessTimes(process, &mut c, &mut e, &mut k, &mut u) } == 0 { return None; }
    let ticks = (u64::from(c.high) << 32 | u64::from(c.low)).checked_sub(EPOCH_DELTA)?;
    Some(u128::from(ticks) * 100)
}

pub fn own_start_ns() -> Option<u128> {
    // SAFETY: the pseudo-handle for this process needs no close.
    process_start_ns(unsafe { GetCurrentProcess() })
}

/// `major.minor.build` from the kernel, not the compatibility-shimmed version APIs.
pub fn os_build() -> Option<String> {
    let mut v = OsVersionInfo { size: std::mem::size_of::<OsVersionInfo>() as u32, major: 0, minor: 0, build: 0, platform: 0, csd: [0; 128] };
    // SAFETY: a sized, writable OSVERSIONINFOW.
    (unsafe { RtlGetVersion(&mut v) } == 0).then(|| format!("{}.{}.{}", v.major, v.minor, v.build))
}

const SYNCHRONIZE: u32 = 0x0010_0000;
const FILE_READ_ATTRIBUTES: u32 = 0x80;
const DIR_ACCESS: u32 = 0x1 | 0x2 | 0x4 | 0x20 | FILE_READ_ATTRIBUTES | SYNCHRONIZE; // list, add file/subdir, traverse
const FILE_WRITE: u32 = 0x2 | 0x4 | FILE_READ_ATTRIBUTES | SYNCHRONIZE; // write/append data
/// Read and write sharing only: without FILE_SHARE_DELETE nobody can rename or delete
/// a held directory or file for as long as the app holds it.
pub const SHARE_NO_DELETE: u32 = 0x1 | 0x2;
const FILE_SHARE_READ: u32 = 0x1;
const FILE_OPEN: u32 = 1;
const FILE_CREATE: u32 = 2;
const FILE_OPEN_IF: u32 = 3;
const FILE_DIRECTORY_FILE: u32 = 0x1;
const FILE_SYNCHRONOUS_IO_NONALERT: u32 = 0x20;
const FILE_NON_DIRECTORY_FILE: u32 = 0x40;
const FILE_OPEN_REPARSE_POINT: u32 = 0x0020_0000;
const OBJ_CASE_INSENSITIVE: u32 = 0x40;
const STATUS_OBJECT_NAME_COLLISION: u32 = 0xC000_0035;
pub const REPARSE: u32 = 0x400;
/// CreateFile flags for opening a directory itself, never what a reparse point names.
pub const OPEN_DIRECTORY_ITSELF: u32 = 0x0200_0000 | 0x0020_0000; // BACKUP_SEMANTICS | OPEN_REPARSE_POINT
pub const DIR_OPEN_ACCESS: u32 = DIR_ACCESS;

/// One leaf name relative to `parent`'s handle. The name is never a path: no separator.
fn create_at(parent: &File, leaf: &str, access: u32, share: u32, disposition: u32, options: u32) -> io::Result<File> {
    if leaf.is_empty() || leaf.contains(['\\', '/', ':', '\0']) || leaf == "." || leaf == ".." {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "not a single leaf name"));
    }
    let wide: Vec<u16> = leaf.encode_utf16().collect();
    let name = UnicodeString { length: (wide.len() * 2) as u16, maximum: (wide.len() * 2) as u16, buffer: wide.as_ptr() };
    let attributes = ObjectAttributes { length: std::mem::size_of::<ObjectAttributes>() as u32, root: parent.as_raw_handle(),
        name: &name, attributes: OBJ_CASE_INSENSITIVE, security: std::ptr::null(), qos: std::ptr::null() };
    let mut io_status = IoStatusBlock { status: 0, information: 0 };
    let mut handle: RawHandle = std::ptr::null_mut();
    // SAFETY: every pointer refers to a live local for the duration of the call.
    let status = unsafe { NtCreateFile(&mut handle, access, &attributes, &mut io_status, std::ptr::null(), 0x80, share, disposition,
        options | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT, std::ptr::null(), 0) };
    if status < 0 {
        let code = status as u32;
        let kind = if code == STATUS_OBJECT_NAME_COLLISION { io::ErrorKind::AlreadyExists } else { io::ErrorKind::Other };
        return Err(io::Error::new(kind, format!("NtCreateFile {leaf}: NTSTATUS {code:#010x}")));
    }
    // SAFETY: a fresh handle NtCreateFile just returned, owned from here on.
    let file = unsafe { File::from_raw_handle(handle) };
    plain(&file, options & FILE_DIRECTORY_FILE != 0)?;
    Ok(file)
}

/// What a handle actually names: the expected kind and never a reparse point.
pub fn plain(file: &File, directory: bool) -> io::Result<()> {
    use std::os::windows::fs::MetadataExt;
    let m = file.metadata()?;
    if m.file_attributes() & REPARSE != 0 || m.is_dir() != directory {
        return Err(io::Error::other("not a plain directory or file"));
    }
    Ok(())
}

/// A new directory under `parent`; fails if the name already exists.
pub fn create_dir_at(parent: &File, leaf: &str) -> io::Result<File> {
    create_at(parent, leaf, DIR_ACCESS, SHARE_NO_DELETE, FILE_CREATE, FILE_DIRECTORY_FILE)
}

/// An existing plain directory under `parent`, or a new one.
pub fn open_or_create_dir_at(parent: &File, leaf: &str) -> io::Result<File> {
    create_at(parent, leaf, DIR_ACCESS, SHARE_NO_DELETE, FILE_OPEN_IF, FILE_DIRECTORY_FILE)
}

/// An existing plain directory under `parent` (test inspection only reads through it).
pub fn open_dir_at(parent: &File, leaf: &str) -> io::Result<File> {
    create_at(parent, leaf, DIR_ACCESS, SHARE_NO_DELETE, FILE_OPEN, FILE_DIRECTORY_FILE)
}

/// A new file under `parent` for writing; fails if the name already exists.
pub fn create_file_at(parent: &File, leaf: &str) -> io::Result<File> {
    create_at(parent, leaf, FILE_WRITE, FILE_SHARE_READ, FILE_CREATE, FILE_NON_DIRECTORY_FILE)
}
