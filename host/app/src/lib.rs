//! Digital Tape one-window app (WP-15, APP-1 with annex APP-1A). The app holds no
//! TAPEFS, audio or device knowledge: every outcome comes from a bundled child.
pub mod children;
pub mod diagnostics;
pub mod discovery;
pub mod drops;
pub mod ingest_job;
pub mod jobdir;
pub mod label;
pub mod messages;
pub mod report;
pub mod state;
pub mod bridge;
pub mod win;
