"""
审计工作底稿模板定义
按资产负债表和利润表分类，覆盖主要科目

数据模型：
- sign: 1（正项，如资产原值/收入）| -1（备抵项，如累计折旧/减值准备）
- is_total: 合计行（汇总全部前序行或 source_rows 指定的行）
- is_net: 净额行（按 source_rows × sign 计算）
- source_rows: 显式指定计算所依赖的行 code 列表。为 None 时 is_total 默认汇总前序所有非合计行

从 v3 开始，科目匹配改为按名称而非固定编码：
- subject_names: 模板涉及的科目名称列表，运行时根据实际上传的科目余额表动态匹配编码
- 数据行 code 与 label 一致，作为模板内部标识符
"""

# 通用列定义
STANDARD_COLUMNS = [
    {"key": "unaudited", "label": "未审数", "source": "end_balance"},
    {"key": "adj_debit", "label": "调整借方", "source": "adjustment_debit"},
    {"key": "adj_credit", "label": "调整贷方", "source": "adjustment_credit"},
    {"key": "audited", "label": "审定数", "source": "audited_balance"},
]

# ==================== 辅助函数 ====================

def data_row(label, code=None, sign=1):
    """普通数据行。code 默认与 label 一致，作为模板内部标识符"""
    return {"label": label, "code": code or label, "sign": sign}

def total_row(label, code="TOTAL", source_rows=None):
    """合计行"""
    return {"label": label, "code": code, "is_total": True, "sign": 1, "source_rows": source_rows}

def net_row(label, code="NET", source_rows=None):
    """净额行（含 source_rows 的显式公式）"""
    return {"label": label, "code": code, "is_net": True, "sign": 1, "source_rows": source_rows}

# ==================== 模板定义 ====================

DRAFT_TEMPLATES = {
    # ==================== 资产类 ====================
    "货币资金": {
        "code": "cash",
        "category": "资产",
        "subject_names": ["库存现金", "银行存款", "其他货币资金"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("库存现金"),
            data_row("银行存款"),
            data_row("其他货币资金"),
            total_row("合计"),
        ],
    },

    "交易性金融资产": {
        "code": "trading_fin_assets",
        "category": "资产",
        "subject_names": ["交易性金融资产"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("交易性金融资产"),
            total_row("合计"),
        ],
    },

    "应收票据": {
        "code": "notes_receivable",
        "category": "资产",
        "subject_names": ["应收票据"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应收票据"),
            total_row("合计"),
        ],
    },

    "应收账款": {
        "code": "receivable",
        "category": "资产",
        "subject_names": ["应收账款", "坏账准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应收账款"),
            data_row("坏账准备", sign=-1),
            net_row("应收账款净额", source_rows=["应收账款", "坏账准备"]),
        ],
    },

    "预付账款": {
        "code": "prepaid",
        "category": "资产",
        "subject_names": ["预付账款"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("预付账款"),
            total_row("合计"),
        ],
    },

    "其他应收款": {
        "code": "other_receivable",
        "category": "资产",
        "subject_names": ["其他应收款", "坏账准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("其他应收款"),
            data_row("坏账准备", sign=-1),
            net_row("其他应收款净额", source_rows=["其他应收款", "坏账准备"]),
        ],
    },

    "合同资产": {
        "code": "contract_assets",
        "category": "资产",
        "subject_names": ["合同资产", "合同资产减值准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("合同资产"),
            data_row("合同资产减值准备", sign=-1),
            net_row("合同资产净额", source_rows=["合同资产", "合同资产减值准备"]),
        ],
    },

    "合同结算": {
        "code": "contract_settlement",
        "category": "资产",
        "subject_names": ["合同结算"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("合同结算"),
            total_row("合计"),
        ],
    },

    "存货": {
        "code": "inventory",
        "category": "资产",
        "subject_names": [
            "材料采购", "在途物资", "原材料", "材料成本差异",
            "库存商品", "发出商品", "商品进销差价",
            "委托加工物资", "周转材料", "消耗性生物资产",
            "存货跌价准备",
        ],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("材料采购"),
            data_row("在途物资"),
            data_row("原材料"),
            data_row("材料成本差异"),
            data_row("库存商品"),
            data_row("发出商品"),
            data_row("商品进销差价"),
            data_row("委托加工物资"),
            data_row("周转材料"),
            data_row("消耗性生物资产"),
            total_row("存货小计", code="SUBTOTAL_1",
                      source_rows=["材料采购", "在途物资", "原材料", "材料成本差异",
                                   "库存商品", "发出商品", "商品进销差价",
                                   "委托加工物资", "周转材料", "消耗性生物资产"]),
            data_row("存货跌价准备", sign=-1),
            net_row("存货净额", source_rows=["SUBTOTAL_1", "存货跌价准备"]),
        ],
    },

    "持有待售资产": {
        "code": "held_for_sale",
        "category": "资产",
        "subject_names": ["持有待售资产"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("持有待售资产"),
            total_row("合计"),
        ],
    },

    "长期股权投资": {
        "code": "lt_equity_invest",
        "category": "资产",
        "subject_names": ["长期股权投资", "长期股权投资减值准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("长期股权投资"),
            data_row("长期股权投资减值准备", sign=-1),
            net_row("长期股权投资净额", source_rows=["长期股权投资", "长期股权投资减值准备"]),
        ],
    },

    "投资性房地产": {
        "code": "invest_property",
        "category": "资产",
        "subject_names": ["投资性房地产", "投资性房地产累计折旧", "投资性房地产减值准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("投资性房地产"),
            data_row("投资性房地产累计折旧", sign=-1),
            data_row("投资性房地产减值准备", sign=-1),
            net_row("投资性房地产净值", source_rows=["投资性房地产", "投资性房地产累计折旧", "投资性房地产减值准备"]),
        ],
    },

    "固定资产": {
        "code": "fixed_assets",
        "category": "资产",
        "subject_names": [
            "固定资产", "累计折旧", "固定资产减值准备",
            "在建工程", "工程物资", "固定资产清理",
            "在建工程减值准备", "工程物资减值准备",
            "生产性生物资产",
        ],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("固定资产", code="固定资产原值"),
            data_row("累计折旧", sign=-1),
            data_row("固定资产减值准备", sign=-1),
            net_row("固定资产净值", code="NET_1",
                    source_rows=["固定资产原值", "累计折旧", "固定资产减值准备"]),
            data_row("在建工程"),
            data_row("工程物资"),
            data_row("固定资产清理"),
            data_row("在建工程减值准备", sign=-1),
            data_row("工程物资减值准备", sign=-1),
            data_row("生产性生物资产"),
        ],
    },

    "使用权资产": {
        "code": "rou_assets",
        "category": "资产",
        "subject_names": ["使用权资产", "使用权资产累计折旧", "使用权资产减值准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("使用权资产"),
            data_row("使用权资产累计折旧", sign=-1),
            data_row("使用权资产减值准备", sign=-1),
            net_row("使用权资产净值", source_rows=["使用权资产", "使用权资产累计折旧", "使用权资产减值准备"]),
        ],
    },

    "无形资产": {
        "code": "intangible",
        "category": "资产",
        "subject_names": ["无形资产", "累计摊销", "无形资产减值准备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("无形资产"),
            data_row("累计摊销", sign=-1),
            data_row("无形资产减值准备", sign=-1),
            net_row("无形资产净值", source_rows=["无形资产", "累计摊销", "无形资产减值准备"]),
        ],
    },

    "长期待摊费用": {
        "code": "lt_prepaid",
        "category": "资产",
        "subject_names": ["长期待摊费用"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("长期待摊费用"),
            total_row("合计"),
        ],
    },

    "递延所得税资产": {
        "code": "deferred_tax_asset",
        "category": "资产",
        "subject_names": ["递延所得税资产"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("递延所得税资产"),
            total_row("合计"),
        ],
    },

    "其他非流动资产": {
        "code": "other_nca",
        "category": "资产",
        "subject_names": ["其他非流动资产"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("其他非流动资产"),
            total_row("合计"),
        ],
    },

    "内部往来": {
        "code": "internal_transactions",
        "category": "资产",
        "subject_names": ["内部往来"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("内部往来"),
            total_row("合计"),
        ],
    },

    # ==================== 负债类 ====================
    "短期借款": {
        "code": "short_borrowing",
        "category": "负债",
        "subject_names": ["短期借款"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("短期借款"),
            total_row("合计"),
        ],
    },

    "交易性金融负债": {
        "code": "trading_fin_liab",
        "category": "负债",
        "subject_names": ["交易性金融负债"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("交易性金融负债"),
            total_row("合计"),
        ],
    },

    "应付票据": {
        "code": "notes_payable",
        "category": "负债",
        "subject_names": ["应付票据"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应付票据"),
            total_row("合计"),
        ],
    },

    "应付账款": {
        "code": "payable",
        "category": "负债",
        "subject_names": ["应付账款"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应付账款"),
            total_row("合计"),
        ],
    },

    "预收账款/合同负债": {
        "code": "contract_liab",
        "category": "负债",
        "subject_names": ["预收账款", "合同负债"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("预收账款"),
            data_row("合同负债"),
            total_row("合计"),
        ],
    },

    "合同履约成本": {
        "code": "contract_performance_cost",
        "category": "负债",
        "subject_names": ["合同履约成本"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("合同履约成本"),
            total_row("合计"),
        ],
    },

    "应付职工薪酬": {
        "code": "employee_benefits",
        "category": "负债",
        "subject_names": ["应付职工薪酬"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应付职工薪酬"),
            total_row("合计"),
        ],
    },

    "应交税费": {
        "code": "taxes_payable",
        "category": "负债",
        "subject_names": ["应交税费"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应交税费"),
            total_row("合计"),
        ],
    },

    "应付股利/应付利息": {
        "code": "dividends_interest_payable",
        "category": "负债",
        "subject_names": ["应付股利", "应付利润", "应付利息"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应付股利"),
            data_row("应付利息"),
            total_row("合计"),
        ],
    },

    "其他应付款": {
        "code": "other_payable",
        "category": "负债",
        "subject_names": ["其他应付款"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("其他应付款"),
            total_row("合计"),
        ],
    },

    "持有待售负债": {
        "code": "held_for_sale_liab",
        "category": "负债",
        "subject_names": ["持有待售负债"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("持有待售负债"),
            total_row("合计"),
        ],
    },

    "长期借款": {
        "code": "lt_borrowing",
        "category": "负债",
        "subject_names": ["长期借款"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("长期借款"),
            total_row("合计"),
        ],
    },

    "应付债券": {
        "code": "bonds_payable",
        "category": "负债",
        "subject_names": ["应付债券"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("应付债券"),
            total_row("合计"),
        ],
    },

    "租赁负债": {
        "code": "lease_liab",
        "category": "负债",
        "subject_names": ["租赁负债"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("租赁负债"),
            total_row("合计"),
        ],
    },

    "长期应付款": {
        "code": "lt_payable",
        "category": "负债",
        "subject_names": ["长期应付款"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("长期应付款"),
            total_row("合计"),
        ],
    },

    "预计负债": {
        "code": "estimated_liab",
        "category": "负债",
        "subject_names": ["预计负债"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("预计负债"),
            total_row("合计"),
        ],
    },

    "递延所得税负债": {
        "code": "deferred_tax_liab",
        "category": "负债",
        "subject_names": ["递延所得税负债"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("递延所得税负债"),
            total_row("合计"),
        ],
    },

    # ==================== 权益类 ====================
    "实收资本": {
        "code": "paid_in_capital",
        "category": "权益",
        "subject_names": ["实收资本", "股本"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("实收资本", code="实收资本（股本）"),
            total_row("合计"),
        ],
    },

    "资本公积": {
        "code": "capital_reserve",
        "category": "权益",
        "subject_names": ["资本公积"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("资本公积"),
            total_row("合计"),
        ],
    },

    "其他综合收益": {
        "code": "other_comprehensive",
        "category": "权益",
        "subject_names": ["其他综合收益"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("其他综合收益"),
            total_row("合计"),
        ],
    },

    "专项储备": {
        "code": "safety_reserve",
        "category": "权益",
        "subject_names": ["专项储备"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("专项储备"),
            total_row("合计"),
        ],
    },

    "盈余公积": {
        "code": "surplus_reserve",
        "category": "权益",
        "subject_names": ["盈余公积"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("盈余公积"),
            total_row("合计"),
        ],
    },

    "未分配利润": {
        "code": "retained_earnings",
        "category": "权益",
        "subject_names": ["本年利润", "利润分配"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("本年利润"),
            data_row("利润分配"),
            total_row("合计"),
        ],
    },

    # ==================== 损益类 ====================
    "营业收入": {
        "code": "revenue",
        "category": "损益",
        "subject_names": ["主营业务收入", "其他业务收入"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("主营业务收入"),
            data_row("其他业务收入"),
            total_row("合计"),
        ],
    },

    "营业成本": {
        "code": "cost",
        "category": "损益",
        "subject_names": ["主营业务成本", "其他业务成本"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("主营业务成本"),
            data_row("其他业务成本"),
            total_row("合计"),
        ],
    },

    "税金及附加": {
        "code": "tax_surcharge",
        "category": "损益",
        "subject_names": ["税金及附加"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("税金及附加"),
            total_row("合计"),
        ],
    },

    "销售费用": {
        "code": "selling_expense",
        "category": "损益",
        "subject_names": ["销售费用"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("销售费用"),
            total_row("合计"),
        ],
    },

    "管理费用": {
        "code": "admin_expense",
        "category": "损益",
        "subject_names": ["管理费用"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("管理费用"),
            total_row("合计"),
        ],
    },

    "财务费用": {
        "code": "finance_expense",
        "category": "损益",
        "subject_names": ["财务费用"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("财务费用"),
            total_row("合计"),
        ],
    },

    "其他收益": {
        "code": "other_income",
        "category": "损益",
        "subject_names": ["其他收益"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("其他收益"),
            total_row("合计"),
        ],
    },

    "投资收益": {
        "code": "invest_income",
        "category": "损益",
        "subject_names": ["投资收益"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("投资收益"),
            total_row("合计"),
        ],
    },

    "公允价值变动损益": {
        "code": "fair_value_change",
        "category": "损益",
        "subject_names": ["公允价值变动损益", "公允价值变动收益"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("公允价值变动损益"),
            total_row("合计"),
        ],
    },

    "资产减值损失": {
        "code": "impairment_loss",
        "category": "损益",
        "subject_names": ["资产减值损失"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("资产减值损失"),
            total_row("合计"),
        ],
    },

    "信用减值损失": {
        "code": "credit_impairment",
        "category": "损益",
        "subject_names": ["信用减值损失"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("信用减值损失"),
            total_row("合计"),
        ],
    },

    "资产处置损益": {
        "code": "asset_disposal",
        "category": "损益",
        "subject_names": ["资产处置损益", "资产处置收益"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("资产处置损益"),
            total_row("合计"),
        ],
    },

    "营业外收入": {
        "code": "non_op_income",
        "category": "损益",
        "subject_names": ["营业外收入"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("营业外收入"),
            total_row("合计"),
        ],
    },

    "营业外支出": {
        "code": "non_op_expense",
        "category": "损益",
        "subject_names": ["营业外支出"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("营业外支出"),
            total_row("合计"),
        ],
    },

    "所得税费用": {
        "code": "income_tax",
        "category": "损益",
        "subject_names": ["所得税费用", "所得税"],
        "columns": STANDARD_COLUMNS,
        "rows": [
            data_row("所得税费用"),
            total_row("合计"),
        ],
    },
}
