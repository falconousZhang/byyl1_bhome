// 规则 3.5 — 函数调用
// <因子> -> <ID> '(' <实参列表> ')'
// 演示：无参调用、单参调用、多参调用、调用结果参与运算、嵌套调用

fn zero() -> i32 {
    0
}

fn identity(a: i32) -> i32 {
    a
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn mul(a: i32, b: i32) -> i32 {
    a * b
}

fn program_3_5(mut x: i32, mut y: i32) -> i32 {
    let mut a: i32 = zero();
    let mut b: i32 = identity(x);
    let mut c: i32 = add(x, y);
    let mut d: i32 = add(x, mul(y, 2));
    a + b + c + d
}
#
