// 规则 3.4 — 比较运算（扩展 3.1）
// 运算符：== | != | > | >= | < | <=
// 演示：各种比较运算符（常用于 if/while 条件）

// 比较运算符用于条件判断，返回类型为 bool（用在 if/while/loop 条件中）
fn max2(mut a: i32, mut b: i32) -> i32 {
    if a >= b { return a; }
    return b;
}

fn min2(mut a: i32, mut b: i32) -> i32 {
    if a <= b { return a; }
    return b;
}

fn program_3_4(mut a: i32, mut b: i32) -> i32 {
    if a == b { return 0; }
    if a != b { return max2(a, b) - min2(a, b); }
    return 0;
}
#
