// 规则 5.4 — break 和 continue（扩展 1.2）
// <语句> -> break ';' | continue ';'
// 演示：循环体内的 break / continue（来自 PDF 示例 program_5_40）

fn program_5_40() {
    while 1==0 { continue; }
    while 1==1 { break; }
}

fn program_5_41(mut n:i32) {
    while n>0 {
        if n==5 {
            break;
        }
        n = n-1;
        continue;
    }
}
#
