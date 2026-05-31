// 错误示例 9.2 / 9.3 — 元组字面量大小与类型错误，以及字段越界
// 预期语义错误：
//   (1) 初始化元素数量与元组声明不一致
//   (2) 初始化元素类型与元组对应位置类型不一致
//   (3) 元组字段索引越界

fn err_tuple_wrong_count(mut a: i32) {
    let mut b: (i32, i32);
    b = (1, 2, 3);
}

fn err_tuple_wrong_type() {
    let mut a: (i32,);
    a = (1 == 1,);
}

fn err_tuple_field_oob() {
    let mut a: (i32, i32) = (1, 2);
    let mut b: i32 = a.2;
}
#
