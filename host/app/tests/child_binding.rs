//! The app's child binding against a REAL `ingest` with the APP-1A report surface
//! (S1). CI points DT_TEST_INGEST at that binary and DT_TEST_INGEST_VERSION at its
//! version string; these are test inputs, read only here, never by the app. Without
//! them the test fails rather than passing silently.

use dtapp::ingest_job;
use dtapp::jobdir;
use dtapp::report::Reading;
use dtapp::state::{App, Next};
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

fn child() -> (PathBuf, String) {
    let bin = std::env::var("DT_TEST_INGEST").expect("DT_TEST_INGEST: path to the S1 ingest binary");
    let ver = std::env::var("DT_TEST_INGEST_VERSION").expect("DT_TEST_INGEST_VERSION");
    (PathBuf::from(bin), ver)
}

fn wav(p: &Path, seconds: u32) {
    let frames = 44100 * seconds;
    let mut d = Vec::with_capacity(frames as usize * 4);
    for i in 0..frames {
        let v = ((i as f64 * 0.05).sin() * 6000.0) as i16;
        d.extend_from_slice(&v.to_le_bytes());
        d.extend_from_slice(&v.to_le_bytes());
    }
    let mut h = Vec::new();
    h.extend_from_slice(b"RIFF");
    h.extend_from_slice(&(36 + d.len() as u32).to_le_bytes());
    h.extend_from_slice(b"WAVEfmt ");
    for v in [16u32] {
        h.extend_from_slice(&v.to_le_bytes());
    }
    h.extend_from_slice(&1u16.to_le_bytes());
    h.extend_from_slice(&2u16.to_le_bytes());
    h.extend_from_slice(&44100u32.to_le_bytes());
    h.extend_from_slice(&176400u32.to_le_bytes());
    h.extend_from_slice(&4u16.to_le_bytes());
    h.extend_from_slice(&16u16.to_le_bytes());
    h.extend_from_slice(b"data");
    h.extend_from_slice(&(d.len() as u32).to_le_bytes());
    h.extend_from_slice(&d);
    std::fs::write(p, h).unwrap();
}

fn scratch(tag: &str) -> PathBuf {
    let t = std::env::temp_dir().join(format!("dtapp-bind-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&t);
    std::fs::create_dir_all(&t).unwrap();
    t
}

/// One drop through the real state machine and the real child.
fn drop_and_check(app: &mut App, data: &Path, folders: &[PathBuf]) -> ingest_job::Outcome {
    let (bin, ver) = child();
    assert_eq!(app.dropped(folders), Next::RunIngest);
    let job = jobdir::create(data, &format!("t{}", dtapp::children::nonce())).unwrap();
    let o = ingest_job::run(&bin, &ver, &job, &app.folders, Arc::new(AtomicBool::new(false)));
    app.finished(&o);
    assert!(jobdir::remove(&job));
    o
}

#[test]
fn success_bar_comes_from_the_published_manifest() {
    let t = scratch("ok");
    let f = t.join("Road Trip");
    std::fs::create_dir_all(&f).unwrap();
    wav(&f.join("01 Song.wav"), 3);
    let mut app = App::default();
    let o = drop_and_check(&mut app, &t.join("data"), &[f]);
    assert_eq!(o.exit, Some(0), "stderr: {}", o.stderr);
    assert!(matches!(o.reading, Reading::Usable { refusal: None, .. }), "{:?}", o.reading);
    assert_eq!(o.total_frames, Some(3 * 44100));
    let v = app.view();
    assert_eq!(v.view, "ready");
    assert!(v.bar.unwrap() > 0.0 && !v.make_enabled);
    std::fs::remove_dir_all(&t).unwrap();
}

#[test]
fn refusals_reach_their_rows_by_id_not_text() {
    let t = scratch("refuse");
    let f = t.join("Bedtime");
    std::fs::create_dir_all(&f).unwrap();
    std::fs::write(f.join("notes.txt"), b"not audio\n").unwrap();
    let mut app = App::default();
    let o = drop_and_check(&mut app, &t.join("data"), &[f]);
    assert_eq!(o.exit, Some(2));
    let Reading::Usable { refusal: Some(r), .. } = &o.reading else { panic!("{:?}", o.reading) };
    assert_eq!(r.id, "SOURCE_NOT_AUDIO");
    assert_eq!(
        app.view().message.unwrap(),
        "The folder \"Bedtime\" has something in it that isn't music. Use a folder with only songs in it."
    );
    assert!(app.details.starts_with("ingest: refused:"), "Show details is the raw stderr");

    let e = t.join("Empty");
    std::fs::create_dir_all(&e).unwrap();
    let mut app = App::default();
    let o = drop_and_check(&mut app, &t.join("data"), &[e]);
    let Reading::Usable { refusal: Some(r), .. } = &o.reading else { panic!("{:?}", o.reading) };
    assert_eq!((o.exit, r.id.as_str()), (Some(2), "FOLDER_EMPTY"));
    std::fs::remove_dir_all(&t).unwrap();
}

#[test]
fn a_wrong_version_pin_falls_back_to_the_generic_row() {
    let t = scratch("pin");
    let f = t.join("X");
    std::fs::create_dir_all(&f).unwrap();
    std::fs::write(f.join("a.txt"), b"x").unwrap();
    let (bin, _) = child();
    let job = jobdir::create(&t.join("data"), "j").unwrap();
    let o = ingest_job::run(&bin, "not the bundled version", &job, &[f], Arc::new(AtomicBool::new(false)));
    assert_eq!(o.exit, Some(2));
    assert!(matches!(o.reading, Reading::Unusable(_)));
    std::fs::remove_dir_all(&t).unwrap();
}

#[test]
fn a_file_drop_adds_nothing_and_starts_no_child() {
    let t = scratch("file");
    std::fs::write(t.join("song.wav"), b"x").unwrap();
    let mut app = App::default();
    assert_eq!(app.dropped(&[t.join("song.wav")]), Next::Nothing);
    assert_eq!(app.view().message.unwrap(), "Drop a folder of music, not single songs.");
    assert!(app.folders.is_empty());
    std::fs::remove_dir_all(&t).unwrap();
}
