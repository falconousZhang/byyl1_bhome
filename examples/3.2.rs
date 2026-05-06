// 规则 3.2 — 加减运算（扩展 3.1）
// <加减表达式> -> <加减表达式> '+' <项>
//              | <加减表达式> '-' <项>
// 演示：加法、减法、链式加减

fn program_3_2(mut a:i32, mut b:i32) -> i32 {
    let mut c:i32 = a + b;
    let mut d:i32 = a - b;
    let mut e:i32 = a + b - a + 1;
    return c + d + e;
}
#
