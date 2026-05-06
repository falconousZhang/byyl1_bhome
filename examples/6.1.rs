// 规则 6.1 — 变量不可变属性（扩展 0.1）
// <变量属性> -> 空
// 演示：省略 mut，变量默认不可变；赋值给不可变变量应报语义错误

fn program_6_10() {
    let a:i32;       // with rule 2.1
    let b;           // with rule 2.1
    let c:i32 = 1;   // with rule 2.3
    let d = 2;       // with rule 2.3
}

// 语义错误示例（取消注释可测试 羁绊C）:
// fn bad() {
//     let a:i32 = 1;
//     a = 2;   // ERROR: cannot assign to immutable variable 'a'
// }
#
