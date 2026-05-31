// 错误示例 7.4 — loop 循环表达式 break 类型不一致
// 预期语义错误：
//   (1) 同一 loop 中 break 有值与无值混用
//   (2) 同一 loop 中两个 break 返回类型不一致（i32 vs bool-like）

fn err_break_mixed() {
    let mut a = loop {
        if 1 == 1 {
            break 1;
        }
        break;
    };
}
#
