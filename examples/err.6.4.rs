// 错误示例 6.4 — 解引用赋值错误
// 预期语义错误：
//   (1) 不可变引用不能通过解引用修改数据
//   (2) 对非引用类型解引用赋值（类型不兼容）

fn err_write_through_imm_ref() {
    let mut a: i32 = 1;
    let b = &a;
    *b = 2;
}

fn err_deref_non_ref(mut a: i32) {
    *a = 5;
}
#
