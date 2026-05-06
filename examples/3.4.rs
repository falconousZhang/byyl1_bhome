// 规则 3.4 — 比较运算（扩展 3.1）
// 运算符：== | != | > | >= | < | <=
// 演示：各种比较运算符（常用于 if/while 条件）

fn program_3_4(mut a:i32, mut b:i32) -> i32 {
    let mut r1:i32 = a == b;
    let mut r2:i32 = a != b;
    let mut r3:i32 = a >  b;
    let mut r4:i32 = a >= b;
    let mut r5:i32 = a <  b;
    let mut r6:i32 = a <= b;
    return r1 + r2 + r3 + r4 + r5 + r6;
}
#
