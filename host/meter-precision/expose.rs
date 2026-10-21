
// Appended test-only access. Original at/grid4 arithmetic is not edited.
pub fn s513hex(b: &[u8]) -> String { b.iter().map(|x|format!("{x:02x}")).collect() }
impl TruePeak {
    pub fn s513eval(&self,x:&[f32],n:i64,q:usize) {
        let at=self.at(x,n,q);let grid=self.grid4(x,n);
        crate::trace(format!("{{\"kind\":\"evaluation\",\"n0\":{n},\"q\":{q},\"at_le\":\"{}\",\"grid_le\":[\"{}\",\"{}\",\"{}\",\"{}\"],\"grid_at_abs_le\":[\"{}\",\"{}\",\"{}\",\"{}\"]}}",s513hex(&at.to_le_bytes()),s513hex(&grid[0].to_le_bytes()),s513hex(&grid[1].to_le_bytes()),s513hex(&grid[2].to_le_bytes()),s513hex(&grid[3].to_le_bytes()),s513hex(&self.at(x,n,0).abs().to_le_bytes()),s513hex(&self.at(x,n,64).abs().to_le_bytes()),s513hex(&self.at(x,n,128).abs().to_le_bytes()),s513hex(&self.at(x,n,192).abs().to_le_bytes())));
    }
    pub fn s513coeff(&self,path:&str) {
        use std::io::Write;
        let mut f=std::fs::OpenOptions::new().write(true).create_new(true).open(path).unwrap();
        for c in &self.taps {f.write_all(&c.to_le_bytes()).unwrap();}
    }
}
