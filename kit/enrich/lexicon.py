# -*- coding: utf-8 -*-
"""
Từ vựng & luật phân loại cho các dashboard sáng tạo (dữ liệu thuần, không logic).

Tách riêng khỏi `normalize.py`/analyzer để: (1) người làm nội dung sửa được từ
khoá mà không phải đọc code phân tích, (2) mỗi luật đứng cạnh ví dụ thật đã rút
từ `data/`, nên khi kết quả lệch thì biết sửa ở đâu.

TẤT CẢ đều rule-based, chạy offline — dự án không có LLM (`.env` chưa có key
thật), và phân cụm phải tất định để báo cáo lặp lại được.

Văn bản đầu vào của các luật ở đây LUÔN đã `.lower()`.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# HOOK TYPE — kiểu câu mở đầu (Hook Lab, cho người viết kịch bản)
# ---------------------------------------------------------------------------
# Đơn nhãn, xét theo THỨ TỰ trong tuple (khớp trước thắng) vì nhiều hook mang
# đồng thời nhiều dấu hiệu và ta muốn nhãn "mạnh" nhất về mặt bán hàng.
# Mỗi nhãn: (tên, [chuỗi con], [regex]) — ví dụ thật ghi trong comment.
HOOK_TYPE_RULES: tuple[tuple[str, list[str], list[str]], ...] = (
    # "99%程序员做副业，都是浪费时间" · "根本不可行，别再被割韭菜了"
    # Xếp ĐẦU TIÊN: bài phủ định hay dùng câu hỏi tu từ ("学Python接单？根本不可行"),
    # nếu để dưới "câu hỏi" thì dấu ? sẽ chiếm nhãn của góc phủ định.
    ("phủ định/nghịch lý",
     ["别再", "千万别", "根本不", "不可行", "浪费时间", "浪费生命", "割韭菜",
      "智商税", "骂醒", "死了这条心", "劝退", "避坑", "幸存者偏差"],
     [r"\d+%.*(都是|全是)"]),

    # "不上班怎么赚钱？" · "有什么副业可以增加收入？？？？"
    # Trên "số liệu": câu hỏi mở đầu là góc chính, dù thân bài có nêu con số
    # ("不上班怎么赚钱？探访月入5k-40w元" vẫn là bài hỏi-đáp).
    # CỐ Ý không dùng từ khoá `如何` trần: "我是如何活下来的" là lời kể chứ không
    # phải câu hỏi. "how to" đã được bắt ở tầng FORMAT (`tutorial`).
    ("câu hỏi",
     ["有什么", "怎么办", "怎么赚", "怎么学", "怎么做", "请问", "在哪", "哪种",
      "可以吗", "是不是", "有没有", "为什么"],
     [r"[？?]"]),

    # "今日战绩800" · "月赚167万" · "首月+2.1W" · "副业月入3000"
    ("số liệu/kết quả",
     ["战绩", "月入", "月赚", "日入", "时薪", "到账", "入账", "收益", "变现"],
     [r"[+＋]?\d[\d.,]*\s*(w|万|k|元|块|美金)", r"(赚|挣|到手|收入|营收)\s*\d",
      r"\$\s*\d"]),

    # "【建议收藏】" · "先码再学" · "速来" · "拿走不谢" · "加入我们"
    ("mệnh lệnh/CTA",
     ["建议收藏", "先码", "码住", "存下", "收藏", "速来", "快来", "听劝",
      "拿走不谢", "抄作业", "加入我们"],
     []),

    # "8个程序员兼职接单平台" · "9种副业真实测试"
    # Xếp TRÊN "danh tính/tuổi": số + lượng từ ở đầu câu là dấu hiệu cụ thể hơn,
    # nếu để dưới thì "8个程序员..." bị gán thành danh tính (do có 程序员).
    ("liệt kê", [],
     [r"^\D{0,6}\d+\s*(个|种|款|条|招|大|平台|软件|方法|网站|工具|集)"]),

    # "35岁程序员，副业月入3000" · "97年程序员" · "27岁程序员"
    # Chỉ tính khi nằm ở ĐẦU câu (8 ký tự đầu) — danh tính là cách mở, còn nằm
    # giữa câu thì chỉ là mô tả.
    ("danh tính/tuổi", [],
     [r"^.{0,8}(\d{2}岁|\d{2}年生|\d{2}后)",
      r"^.{0,8}(程序员|打工人|学生党|新手小白|宝妈|大学生)"]),

    # "深扒" · "拆解AI漫剧全流程" · "复盘我是如何活下来的" · "探访月入5k"
    ("bóc tách/độc quyền",
     ["深扒", "拆解", "复盘", "揭秘", "内幕", "真实现状", "亲身经历", "探访",
      "采访", "公开"],
     []),

    # "限时" · "最后一次" · "90分钟拆解" · "七天就能"
    ("khẩn cấp/thời gian",
     ["限时", "最后", "仅剩", "马上", "即将"],
     [r"\d+\s*(分钟|小时|天|周)就"]),

    # "放假也不敢休息" · "爆肝2个月" · "不想上班"
    ("cảm xúc/nỗi đau",
     ["后悔", "心酸", "太累", "爆肝", "不想上班", "焦虑", "害怕", "内卷",
      "熬夜", "不敢"],
     []),
)

OTHER_HOOK = "khác"

# Ký tự cắt câu mở đầu (hook chỉ là mệnh đề đầu, không phải cả caption)
HOOK_BREAK_CHARS = "，,。！!？?\n｜|·；;、"

# ---------------------------------------------------------------------------
# VOICE OF CUSTOMER — cụm nỗi đau (đa nhãn) cho sheet PAIN_POINTS
# ---------------------------------------------------------------------------
# Rút từ bình luận thật trong `data/bili/json/` và `data/weibo/json/`.
# `hook_goi_y` là template VIẾT TAY (tất định, sửa được) — không phải LLM sinh.
PAIN_FAMILIES: tuple[tuple[str, list[str], str], ...] = (
    ("thu nhập thấp / không đủ sống",
     ["存不到钱", "温饱", "工资低", "不够花", "没钱", "太穷", "穷死",
      "养不起", "房贷", "月光"],
     "Đi làm đủ sống nhưng không dư — đây là cách {product} tạo dòng thu nhập thứ hai"),

    ("sợ mất việc / tuổi 35",
     ["优化", "裁员", "失业", "被淘汰", "转型", "35岁", "中年", "毕业即"],
     "Nếu mai mất việc thì sống bằng gì? Chuẩn bị trước bằng {product}"),

    ("quá tải / kiệt sức",
     ["太累", "肝不动", "熬夜", "加班", "没时间", "没精力", "痛苦", "内卷",
      "身体吃不消"],
     "Không cần thêm giờ làm — {product} chạy được cả khi bạn đã kiệt sức"),

    ("không biết bắt đầu từ đâu",
     ["怎么开始", "从哪", "零基础", "小白", "不知道", "没方向", "无从下手",
      "求带", "怎么学"],
     "Bắt đầu từ đâu? Đây là bước 1 cụ thể với {product}"),

    ("không có khách / không có traffic",
     ["没客户", "获客", "没流量", "单子从哪", "没人问", "接不到", "没订单"],
     "Có kỹ năng mà không có khách — {product} giải quyết đúng khúc này"),

    ("sợ bị lừa / mất tiền",
     ["骗", "割韭菜", "卖课", "反诈", "押金", "智商税", "套路", "不靠谱"],
     "Không bán khoá học, không thu phí trước — đây là bằng chứng thật của {product}"),

    ("thiếu kỹ năng / cạnh tranh",
     ["不会", "没技术", "竞争", "门槛", "天赋", "学不会", "跟不上"],
     "Không cần giỏi từ đầu — {product} hạ ngưỡng vào nghề"),
)

# ---------------------------------------------------------------------------
# OBJECTIONS — phản đối, cho sheet OBJECTIONS
# ---------------------------------------------------------------------------
# (nhãn, [từ khoá], cách xử lý trong script, bằng chứng cần chuẩn bị)
OBJECTIONS: tuple[tuple[str, list[str], str, str], ...] = (
    ("không đáng tin / lừa đảo",
     ["骗", "割韭菜", "假的", "不靠谱", "套路", "智商税", "卖课"],
     "Nói trước điều khách sợ, rồi đưa bằng chứng kiểm chứng được",
     "Ảnh sao kê / lịch sử đơn thật, có che thông tin cá nhân"),

    ("quá khó với tôi",
     ["太难", "学不会", "做不了", "没天赋", "门槛高", "不会"],
     "Chia nhỏ thành bước 1 làm được trong 10 phút",
     "Video thao tác 1 lần không cắt, từ số 0"),

    ("không có thời gian",
     ["没时间", "太忙", "加班", "没精力"],
     "Định vị lại theo thời lượng: mỗi ngày 30 phút",
     "Bảng thời gian thật của 1 tuần"),

    ("sống sót nhờ may mắn",
     ["幸存者偏差", "个例", "运气", "特殊情况"],
     "Đưa cả ca thất bại và tỉ lệ, không chỉ ca thắng",
     "Số liệu nhiều người, gồm cả người bỏ giữa đường"),

    ("thị trường đã bão hoà",
     ["竞争激烈", "太多人做", "红海", "饱和", "卷"],
     "Chỉ ra ngách hẹp còn trống thay vì đánh trực diện",
     "Bản đồ ngách kèm số lượng bài và mức tương tác"),

    ("giá cao / không đủ tiền",
     ["太贵", "没钱", "买不起", "免费"],
     "Đối chiếu chi phí với chi phí của việc KHÔNG làm gì",
     "Bảng so sánh chi phí — hiệu quả"),
)

# ---------------------------------------------------------------------------
# Lọc rác bình luận
# ---------------------------------------------------------------------------
# Spam thật gặp trong dữ liệu: mời gọi kết bạn/quét mã/đăng ký nền tảng
SPAM_PATTERNS: tuple[str, ...] = (
    r"扫码", r"入驻", r"加我", r"私信我", r"^@\w+$", r"加微", r"vx[:：]",
    r"扣1", r"求关注", r"互fo", r"互粉",
)

# Từ vô nghĩa khi thống kê từ khoá (jieba). Cố ý ngắn — thêm dần theo ngành.
STOPWORDS_ZH: frozenset[str] = frozenset("""
的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有
看 好 自己 这 那 什么 怎么 可以 但是 因为 所以 如果 还是 已经 现在 时候
真的 觉得 感觉 知道 觉得 就是 这个 那个 我们 他们 你们 大家 一下 一样
可能 应该 需要 想要 出来 起来 下来 不是 只是 而且 然后 还有 这样 那样
谢谢 哈哈 哈哈哈 嗯 啊 吧 呢 吗 哦 呀 嘛 咯 啦
""".split())

# ---------------------------------------------------------------------------
# Bucket dùng chung cho báo cáo
# ---------------------------------------------------------------------------
# (nhãn, min, max) — max=None là không giới hạn trên
HOOK_LEN_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("≤10 ký tự", 0, 10),
    ("11–20", 11, 20),
    ("21–30", 21, 30),
    (">30", 31, None),
)

IMAGE_COUNT_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("1 ảnh", 1, 1),
    ("2–3 ảnh", 2, 3),
    ("4–5 ảnh", 4, 5),
    ("6+ ảnh", 6, None),
)

HASHTAG_COUNT_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("không hashtag", 0, 0),
    ("1–3", 1, 3),
    ("4–6", 4, 6),
    ("7+", 7, None),
)


def bucket_of(value: float | int | None,
              buckets: tuple[tuple[str, int, int | None], ...]) -> str:
    """Nhãn bucket của 1 giá trị số; ngoài mọi khoảng -> "" ."""
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    for label, lo, hi in buckets:
        if v >= lo and (hi is None or v <= hi):
            return label
    return ""
