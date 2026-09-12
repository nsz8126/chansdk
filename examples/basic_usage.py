"""chansdk 基本使用示例"""

from chan import CChan, KL_TYPE, DATA_SRC


def example_csv_analysis():
    """从 CSV 文件分析缠论"""
    chan = CChan(
        code="000001",
        begin_time=None,
        end_time=None,
        data_src=DATA_SRC.CSV,
        lv_list=[KL_TYPE.K_WEEK, KL_TYPE.K_DAY],
        file_path="./data/000001.csv",
    )

    # 驱动计算
    # 获取日线分析结果
    kline_list = chan[KL_TYPE.K_DAY]
    print(f"K线数量: {sum(len(klc.lst) for klc in kline_list.lst)}")
    print(f"笔数量: {len(kline_list.bi_list)}")
    print(f"线段数量: {len(kline_list.seg_list)}")
    print(f"中枢数量: {len(kline_list.zs_list)}")
    print(f"买卖点数量: {len(kline_list.bs_point_lst)}")

    # 打印买卖点
    for bsp in kline_list.bs_point_lst:
        print(f"  {bsp.type2str()} @ {bsp.klu.time}")


def example_custom_config():
    """使用自定义配置"""
    from chan import CChanConfig

    config = CChanConfig()
    config.bi_conf.bi_algo = "peak"
    config.seg_conf.seg_algo = "chan"

    chan = CChan(
        code="000001",
        data_src=DATA_SRC.CSV,
        lv_list=[KL_TYPE.K_DAY],
        config=config,
        file_path="./data/000001.csv",
    )

    for _ in chan:
        pass

    print("分析完成")


if __name__ == "__main__":
    example_csv_analysis()
