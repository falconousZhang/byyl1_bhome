// 规则 5.0 — 循环语句基础（依赖 5.1 or 5.2 or 5.3，扩展 1.2）
// <语句>     -> <循环语句>
// 演示：while / for / loop 均属于 <循环语句>（此文件仅展示分类）

fn program_5_0_while(mut n:i32) {
    while n>0 {
        n = n-1;
    }
}

fn program_5_0_loop() {
    loop {
    }
}
#
