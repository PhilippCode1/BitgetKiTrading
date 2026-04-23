//! SPSC-Ring (Rohbytes + Arrow-IPC Nutzlast) — Layout identisch zu
//! `shared_py.eventbus.shared_memory.SHARED_MEMORY_LAYOUT_VERSION`.
//!
//! Dient als **Referenz** fuer Low-Latency-Pfade; der produktive Python-Bus nutzt
//! dieselben Konstanten und optional `fcntl`-Locks fuer Multi-Prozess-Korrektheit.

use std::sync::atomic::{fence, AtomicU32, AtomicU64, Ordering};

pub const MAGIC: u64 = 0x42_47_54_5F_53_48_4D_51;
pub const VERSION: u32 = 1;
pub const HEADER_SIZE: usize = 128;
pub const LAYOUT_VERSION: u32 = 1;

const OFF_MAGIC: usize = 0;
const OFF_VERSION: usize = 8;
const OFF_SLOT_COUNT: usize = 12;
const OFF_SLOT_STRIDE: usize = 16;
const OFF_MAX_PAYLOAD: usize = 20;
const OFF_HEAD: usize = 64;
const OFF_TAIL: usize = 72;
const OFF_LAYOUT_VERSION: usize = 24;

#[inline]
pub fn slot_stride(max_payload: u32) -> u32 {
    let body = 8u32.saturating_add(max_payload);
    (body + 7) & !7
}

#[inline]
pub fn region_size(slot_count: u32, max_payload: u32) -> usize {
    let sc = slot_count as usize;
    let stride = slot_stride(max_payload) as usize;
    HEADER_SIZE.saturating_add(sc.saturating_mul(stride))
}

#[inline]
fn slot_base(slot_index: usize, stride: usize) -> usize {
    HEADER_SIZE + slot_index * stride
}

pub fn init_region(buf: &mut [u8], slot_count: u32, max_payload: u32) -> Result<(), &'static str> {
    if slot_count == 0 {
        return Err("slot_count");
    }
    let stride = slot_stride(max_payload) as usize;
    let need = region_size(slot_count, max_payload);
    if buf.len() < need {
        return Err("buffer zu klein");
    }
    buf[..need].fill(0);
    buf[OFF_MAGIC..OFF_MAGIC + 8].copy_from_slice(&MAGIC.to_le_bytes());
    buf[OFF_VERSION..OFF_VERSION + 4].copy_from_slice(&VERSION.to_le_bytes());
    buf[OFF_SLOT_COUNT..OFF_SLOT_COUNT + 4].copy_from_slice(&slot_count.to_le_bytes());
    buf[OFF_SLOT_STRIDE..OFF_SLOT_STRIDE + 4].copy_from_slice(&(stride as u32).to_le_bytes());
    buf[OFF_MAX_PAYLOAD..OFF_MAX_PAYLOAD + 4].copy_from_slice(&max_payload.to_le_bytes());
    buf[OFF_LAYOUT_VERSION..OFF_LAYOUT_VERSION + 4].copy_from_slice(&LAYOUT_VERSION.to_le_bytes());
    unsafe {
        let hp = buf.as_mut_ptr().add(OFF_HEAD) as *mut AtomicU64;
        let tp = buf.as_mut_ptr().add(OFF_TAIL) as *mut AtomicU64;
        std::ptr::write(hp, AtomicU64::new(0));
        std::ptr::write(tp, AtomicU64::new(0));
    }
    Ok(())
}

fn read_u32(buf: &[u8], off: usize) -> u32 {
    u32::from_le_bytes(buf[off..off + 4].try_into().unwrap())
}

fn load_meta(buf: &[u8]) -> Result<(u32, u32, u32), &'static str> {
    if buf.len() < HEADER_SIZE {
        return Err("header");
    }
    let magic = u64::from_le_bytes(buf[OFF_MAGIC..OFF_MAGIC + 8].try_into().unwrap());
    if magic != MAGIC {
        return Err("magic");
    }
    let ver = read_u32(buf, OFF_VERSION);
    if ver != VERSION {
        return Err("version");
    }
    let slot_count = read_u32(buf, OFF_SLOT_COUNT);
    let stride = read_u32(buf, OFF_SLOT_STRIDE);
    let max_payload = read_u32(buf, OFF_MAX_PAYLOAD);
    if slot_count == 0 || stride < 8 {
        return Err("meta");
    }
    Ok((slot_count, stride, max_payload))
}

pub fn try_publish(buf: &mut [u8], payload: &[u8]) -> Result<Option<u64>, &'static str> {
    let (slot_count, stride, max_payload) = load_meta(buf)?;
    if payload.len() > max_payload as usize {
        return Err("payload zu gross");
    }
    let n = slot_count as u64;
    let stride = stride as usize;
    let p = buf.as_mut_ptr();
    unsafe {
        let tail = &*(p.add(OFF_TAIL) as *const AtomicU64);
        let head = &*(p.add(OFF_HEAD) as *const AtomicU64);
        let t = tail.load(Ordering::Acquire);
        let h = head.load(Ordering::Acquire);
        if t.wrapping_sub(h) >= n {
            return Ok(None);
        }
        let idx = (t % n) as usize;
        let sb = slot_base(idx, stride);
        let st = &*(p.add(sb) as *const AtomicU32);
        if st.load(Ordering::Acquire) != 0 {
            return Err("slot nicht leer");
        }
        let len_off = sb + 4;
        let data_off = sb + 8;
        let lenb = (payload.len() as u32).to_le_bytes();
        std::ptr::copy_nonoverlapping(lenb.as_ptr(), p.add(len_off), 4);
        std::ptr::copy_nonoverlapping(payload.as_ptr(), p.add(data_off), payload.len());
        fence(Ordering::Release);
        st.store(1, Ordering::Release);
        let id = t;
        tail.store(t.wrapping_add(1), Ordering::Release);
        Ok(Some(id))
    }
}

pub fn try_consume(buf: &mut [u8]) -> Result<Option<(u64, Vec<u8>)>, &'static str> {
    let (slot_count, stride, max_payload) = load_meta(buf)?;
    let n = slot_count as u64;
    let stride = stride as usize;
    let p = buf.as_mut_ptr();
    unsafe {
        let head = &*(p.add(OFF_HEAD) as *const AtomicU64);
        let tail = &*(p.add(OFF_TAIL) as *const AtomicU64);
        let h = head.load(Ordering::Acquire);
        let t = tail.load(Ordering::Acquire);
        if t == h {
            return Ok(None);
        }
        let idx = (h % n) as usize;
        let sb = slot_base(idx, stride);
        let st = &*(p.add(sb) as *const AtomicU32);
        if st.load(Ordering::Acquire) != 1 {
            return Ok(None);
        }
        let len = u32::from_le_bytes(std::slice::from_raw_parts(p.add(sb + 4), 4).try_into().unwrap()) as usize;
        if len > max_payload as usize {
            return Err("korrupt");
        }
        let data_off = sb + 8;
        let out = std::slice::from_raw_parts(p.add(data_off), len).to_vec();
        st.store(0, Ordering::Release);
        fence(Ordering::Release);
        head.store(h.wrapping_add(1), Ordering::Release);
        Ok(Some((h, out)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let mut b = vec![0u8; region_size(4, 256)];
        init_region(&mut b, 4, 256).unwrap();
        assert!(try_publish(&mut b, b"abc").unwrap().is_some());
        let (_id, v) = try_consume(&mut b).unwrap().unwrap();
        assert_eq!(v, b"abc");
    }
}
