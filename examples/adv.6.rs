// 进阶示例 6 — 函数组合与高阶算法：排序、查找、统计
// 演示函数调用链：helper 函数被多次调用
// 验证：max2(3,7)=7, clamp(15,0,10)=10, sum_range(1,5)=15

fn max2(a: i32, b: i32) -> i32 {
    if a > b {
        return a;
    }
    return b;
}

fn min2(a: i32, b: i32) -> i32 {
    if a < b {
        return a;
    }
    return b;
}

fn abs_val(mut n: i32) -> i32 {
    if n < 0 {
        return -n;
    }
    return n;
}

fn clamp(mut v: i32, mut lo: i32, mut hi: i32) -> i32 {
    return max2(lo, min2(v, hi));
}

fn sum_range(mut lo: i32, mut hi: i32) -> i32 {
    let mut s: i32 = 0;
    let mut i: i32 = lo;
    while i <= hi {
        s = s + i;
        i = i + 1;
    }
    return s;
}

fn dist(a: i32, b: i32) -> i32 {
    return abs_val(a - b);
}
#
