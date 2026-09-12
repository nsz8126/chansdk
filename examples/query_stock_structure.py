"""打印指定标的的缠论结构（笔/线段/中枢/买卖点）。

用法:
    python examples/query_stock_structure.py [code] [kl_type]

依赖 eltdx 数据源（pip install chansdk[eltdx]），需要网络。
"""
import sys

sys.path.insert(0, ".")

from chan import CChan, DATA_SRC, KL_TYPE, AUTYPE


def main(code="002812", kl_type=KL_TYPE.K_1M):
    chan = CChan(
        code=code,
        data_src=DATA_SRC.ELTDX,
        autype=AUTYPE.QFQ,
        lv_list=[kl_type],
        timeout=15.0,
    )

    kl = chan[kl_type]
    print(f"=== {code} {kl_type.name} 缠论结构 ===")
    print(f"K线: {sum(len(klc.lst) for klc in kl.lst)}")
    print(f"笔: {len(kl.bi_list)}")
    print(f"线段: {len(kl.seg_list)}")
    print(f"中枢: {len(kl.zs_list)}")
    print(f"买卖点: {len(kl.bs_point_lst)}")

    print()
    print("--- 笔 ---")
    for i, bi in enumerate(kl.bi_list):
        print(f"  [{i:2d}] {bi}")

    print()
    print("--- 线段 ---")
    for i, seg in enumerate(kl.seg_list):
        print(f"  [{i}] {seg}")

    print()
    print("--- 中枢 ---")
    for i, zs in enumerate(kl.zs_list):
        print(f"  [{i}] {zs}")

    print()
    print("--- 买卖点 ---")
    for i, bsp in enumerate(kl.bs_point_lst.getSortedBspList()):
        print(f"  [{i}] {bsp}")


if __name__ == "__main__":
    arg_code = sys.argv[1] if len(sys.argv) > 1 else "002812"
    arg_kl = KL_TYPE[sys.argv[2]] if len(sys.argv) > 2 else KL_TYPE.K_1M
    main(arg_code, arg_kl)
