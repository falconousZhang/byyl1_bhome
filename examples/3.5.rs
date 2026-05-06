// 规则 3.5 — 复合表达式（多运算符，测试优先级与结合性）
// 综合 3.1~3.4，演示运算符优先级：* / 高于 + - 高于 == != < <= > >=
// 括号可强制改变结合顺序

fn program_3_5(mut a:i32, mut b:i32, mut c:i32) -> i32 {
    // * 优先于 +
    let mut x:i32 = a + b * c;
    // 括号改变优先级
    let mut y:i32 = (a + b) * c;
    // 链式比较
    let mut z:i32 = a * b + c == c + b * a;
    // 嵌套括号
    let mut w:i32 = ((a + 1) * (b - 1)) / c;
    return x + y + z + w;
}
#
