// 规则 3.3 — 乘除运算（扩展 3.1）
// <项> -> <项> '*' <因子>
//       | <项> '/' <因子>
// 演示：乘法、除法、混合加减乘除（运算符优先级）

fn program_3_3(mut a:i32, mut b:i32) -> i32 {
    let mut c:i32 = a * b;
    let mut d:i32 = a / b;
    let mut e:i32 = a + b * 2;
    let mut f:i32 = (a + b) * 2;
    return c + d + e + f;
}
#
