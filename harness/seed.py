"""AlphaHive V3.1.1 - 全局随机种子入口 (单一真理源)

所有随机性操作必须调用本模块，保证基线可复现 (硬约束2 + 回归闸)。
禁止在其他脚本里直接 np.random.seed / random.seed / Math.random。
"""
import hashlib
import numpy as np

MASTER_SEED = 42


def global_rng():
    """全局主 RNG。用于非基线的确定性随机(如打乱顺序)。"""
    return np.random.RandomState(MASTER_SEED)


def baseline_seed(scan_time_utc: str, record_id: str, baseline_type: str) -> int:
    """基线专用稳定哈希种子 (硬约束2)。

    baseline_type ∈ {"candidate_pool_random", "full_pool_random"}
    同一 (scan_time_utc, record_id, baseline_type) 永远得到同一种子 → 基线可复现。
    """
    key = f"{scan_time_utc}{record_id}{baseline_type}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    # 取前 8 位 hex → 32-bit int (numpy RandomState 上限 2**32-1)
    return int(h[:8], 16)


def baseline_rng(scan_time_utc: str, record_id: str, baseline_type: str) -> np.random.RandomState:
    """返回基线专用 RNG。抽标的 + 分配方向都用它。"""
    return np.random.RandomState(baseline_seed(scan_time_utc, record_id, baseline_type))


def random_direction(rng: np.random.RandomState) -> tuple:
    """随机分配方向 (三对齐要求)。返回 (direction_str, direction_sign)。"""
    if rng.rand() < 0.5:
        return "Long", 1
    return "Short", -1


if __name__ == "__main__":
    # 自检：同输入必得同种子
    s1 = baseline_seed("2026-07-07T02:00:00Z", "rec_001", "candidate_pool_random")
    s2 = baseline_seed("2026-07-07T02:00:00Z", "rec_001", "candidate_pool_random")
    assert s1 == s2, "seed 不可复现 = 回归闸会失败"
    s3 = baseline_seed("2026-07-07T02:00:00Z", "rec_001", "full_pool_random")
    assert s1 != s3, "不同 baseline_type 应得不同种子"
    print(f"seed.py self-check PASS: candidate={s1} full={s3}")
