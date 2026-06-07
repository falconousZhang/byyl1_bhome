// 规则 2.0 — 变量声明（依赖 0.1, 0.2）
// <变量声明> -> <变量属性> <ID>
// <变量声明> -> <变量属性> <ID> ':' <类型>
// 演示：带/不带类型注解的变量声明（作为 let 语句的核心）

fn program_2_0() {
    let mut a;      // type inferred from assignment
    a = 1;
    let mut b: i32; // type given via annotation
    b = 2;
}
#
