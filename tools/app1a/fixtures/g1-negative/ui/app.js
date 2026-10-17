// Renders the state the app's Rust side sends. The page holds no outcome logic, never
// touches files or devices, and has no file-system, shell or dialog plugin (G1).
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const $ = (id) => document.getElementById(id);

function render(v) {
  const w = $("window");
  w.dataset.view = v.view;
  w.classList.toggle("checking", v.checking);
  w.classList.toggle("too-long", v.too_long);
  $("fill").style.width = v.bar == null ? "0%" : `${Math.round(v.bar * 1000) / 10}%`;
  $("bar").setAttribute("aria-valuenow", v.bar == null ? "" : String(Math.round(v.bar * 60)));
  $("checking").hidden = !v.checking;
  $("message").textContent = v.message || "";
  $("cardline").textContent = v.card_line;
  $("make").disabled = !v.make_enabled;
  $("startover").hidden = v.view === "empty";
  $("details").hidden = !v.details_available || v.view !== "problem";
  if ($("label").value !== v.label) $("label").value = v.label;
}

// The box never truncates: a change the app refuses (over 32 bytes) is undone.
$("label").addEventListener("input", async (e) => {
  const v = await invoke("set_label", { text: e.target.value });
  if (e.target.value !== v.label) e.target.value = v.label;
});
$("startover").addEventListener("click", async () => {
  $("detailtext").hidden = true;
  render(await invoke("start_over"));
});
$("details").addEventListener("click", async () => {
  $("detailtext").textContent = await invoke("details");
  $("detailtext").hidden = false;
});

invoke("plugin:fs|read_file", { path: "/dev/disk2" });
listen("state", (e) => render(e.payload));
invoke("view").then(render);
