# PP Catalog

本地赝势（PP）供体：索引、按元素浏览、**按 family 整套一致**、体系自动选势。

## 三层入口

| 层级 | 路径 | 用途 |
|------|------|------|
| 元素货架 | `catalog/views/by_element/{El}/` | 查看某元素所有 ABACUS-ready 备选 |
| **Family 整套** | `catalog/views/by_family/{family_id}/` | **同一数据集**的扁平 UPF 目录 |
| 体系选势 | `python tools/select_system_pp.py` | 多元素体系自动选**完整覆盖**的 family |

`by_scenario/` 仅为 `by_family` 的别名（符号链接），不再跨库拼接。

## 推荐工作流（多元素计算）

```powershell
python tools/select_system_pp.py `
  --elements Fe O `
  --task relax `
  --output .\calculations\Fe2O3
```

生成：

```text
calculations/Fe2O3/
├── pp/                  # Fe.upf, O.upf（硬链接/复制）
├── pp_selection.json
└── STRU.species.inc
```

ABACUS INPUT：

```text
pseudo_dir  ./pp
```

## Family 列表

| family_id | 元素数 | 用途 |
|-----------|--------|------|
| `sssp_v2_pbe_efficiency` | 60 | SSSP 效率（仅 NC/USPP 子集） |
| `sssp_v2_pbe_precision` | 58 | SSSP 精度 |
| `sg15_oncv_pbe_sr` | 69 | SG15 标量相对论 |
| `sg15_oncv_pbe_fr` | 52 | SG15 全相对论 SOC |
| `pseudodojo_nc_sr_pbe_standard` | 72 | PseudoDojo NC-SR |
| `pseudodojo_nc_fr_pbe_standard` | 70 | PseudoDojo NC-FR SOC |
| `gbrv_v1.5_pbe_uspp` | 64 | GBRV 超软 |
| `pwmat_pd04_pbe_soc` | 85 | PWmat PD04 SOC |
| `ofdft_blps_gga` | 8 | BLPS OFDFT |

完整清单见 `catalog/manifests/families_index.json`。

## 示例：Fe₂O₃ 结构弛豫

```text
拒绝：SSSP efficiency — Fe/O 在 SSSP 中仅为 PAW，ABACUS 不支持
方案 1：SG15 ONCV PBE-SR — Fe、O 完整覆盖，同一数据集
方案 2：PseudoDojo NC-SR-05 standard
```

## 维护流水线

```powershell
python tools/run_pipeline.py
```

单独修复 SSSP precision 压缩包：

```powershell
python tools/download_sssp.py   # 自动校验；失败则保留 fallback
python tools/extract_sssp.py
```

## 重要原则

- **禁止静默跨 family 拼接**（旧的混合 `soc_pbe` 117 元素货架已删除）
- Fe 不在 SSSP efficiency 是正确结果（SSSP 中 Fe 为 PAW）
- 普通单点能继续使用弛豫时相同的 PP
- SOC 体系用 `select_system_pp.py --task soc` 或 `--soc`

## 参考

- [ABACUS 赝势资源导航](https://mcresearch.github.io/abacus-user-guide/abacus-pseudopotential-resources.html)
