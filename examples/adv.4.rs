// 进阶示例 4 — 复杂控制流：Collatz步数、判素数、数字位数之和
// 验证：collatz_len(27)=111, is_prime(97)=1, is_prime(100)=0, digit_sum(12345)=15

fn collatz_len(mut n: i32) -> i32 {
    let mut steps: i32 = 0;
    while n != 1 {
        let mut rem: i32 = n - n / 2 * 2;
        if rem == 0 {
            n = n / 2;
        } else {
            n = 3 * n + 1;
        }
        steps = steps + 1;
    }
    steps
}

fn is_prime(n: i32) -> i32 {
    if n < 2 {
        return 0;
    }
    if n == 2 {
        return 1;
    }
    let mut rem2: i32 = n - n / 2 * 2;
    if rem2 == 0 {
        return 0;
    }
    let mut i: i32 = 3;
    while i * i <= n {
        let mut r: i32 = n - n / i * i;
        if r == 0 {
            return 0;
        }
        i = i + 2;
    }
    return 1;
}

fn digit_sum(mut n: i32) -> i32 {
    if n < 0 {
        n = -n;
    }
    let mut s: i32 = 0;
    while n > 0 {
        let mut d: i32 = n - n / 10 * 10;
        s = s + d;
        n = n / 10;
    }
    s
}
#
