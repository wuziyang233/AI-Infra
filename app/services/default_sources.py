"""Default RSS sources for AI Infra 决策情报.

Each entry: (name, url, type, category, language, priority, status, description)
"""

DEFAULT_SOURCES = [
    # ── 海外 AI / Infra 信源 ──
    ("HN AI", "https://hnrss.org/newest?q=AI", "rss", "overseas_ai", "en", 5, "active", "Hacker News AI 相关文章"),
    ("HN GPU", "https://hnrss.org/newest?q=GPU", "rss", "overseas_ai", "en", 4, "active", "Hacker News GPU 计算相关"),
    ("HN LLM", "https://hnrss.org/newest?q=LLM", "rss", "overseas_ai", "en", 5, "active", "Hacker News 大模型相关"),
    ("The Batch", "https://www.deeplearning.ai/the-batch/", "rss", "overseas_ai", "en", 5, "pending", "DeepLearning.AI 周报（仅邮件订阅，web 存档页）"),
    ("OpenAI Blog", "https://openai.com/news/rss.xml", "rss", "overseas_ai", "en", 5, "active", "OpenAI 官方新闻 RSS"),
    ("Anthropic News", "https://openrss.org/anthropic.com/news", "rss", "overseas_ai", "en", 5, "pending", "Anthropic 官方新闻（通过 OpenRSS 转换）"),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/", "rss", "overseas_ai", "en", 4, "active", "NVIDIA 官方博客（GPU/AI Infra）"),
    ("Google AI Blog", "https://blog.google/technology/ai/rss/", "rss", "overseas_ai", "en", 4, "active", "Google AI 官方博客"),

    # ── 国内中文 AI / 科技信源 ──
    # RSSHub 路由，需要 RSSHub 实例可访问
    ("机器之心", "https://rsshub.app/jiqizhixin", "rss", "china_ai", "zh", 5, "pending", "机器之心：AI 科技媒体，深度报道 AI 产业"),
    ("量子位", "https://rsshub.app/qbitai", "rss", "china_ai", "zh", 5, "pending", "量子位：AI 前沿科技报道"),
    ("甲子光年", "https://rsshub.app/jazzyear", "rss", "china_ai", "zh", 4, "pending", "甲子光年：科技产业智库媒体"),
    ("36氪 AI 精选", "https://rsshub.app/36kr/motif/ai", "rss", "china_ai", "zh", 5, "pending", "36氪 AI 板块精选内容"),
    ("智东西", "https://rsshub.app/zhidx", "rss", "china_ai", "zh", 4, "pending", "智东西：智能产业媒体"),
    ("InfoQ 中文 AI", "https://rsshub.app/infoq/topic/ai", "rss", "china_ai", "zh", 4, "pending", "InfoQ 中文 AI 专题"),
    ("少数派 AI", "https://rsshub.app/sspai/tag/AI", "rss", "china_ai", "zh", 3, "pending", "少数派 AI 相关文章"),
    ("知乎 AI 精选", "https://rsshub.app/zhihu/topics/19551475", "rss", "china_ai", "zh", 4, "pending", "知乎 AI 话题精选"),
    ("掘金 AI", "https://rsshub.app/juejin/tag/AI", "rss", "china_ai", "zh", 3, "pending", "掘金 AI 技术文章"),

    # ── 公众号 / 中文内容补充（通过 RSSHub）──
    # 使用 wechat 通用抓取路由
    ("AI 科技评论", "https://rsshub.app/wechat/mp/gh_6e0c715cf15c", "rss", "wechat", "zh", 2, "pending", "微信公众号：AI 科技评论"),
    ("腾讯云 AI", "https://rsshub.app/wechat/mp/gh_fe7a3b0a08c4", "rss", "wechat", "zh", 2, "pending", "微信公众号：腾讯云 AI 产品动态"),
    ("阿里云 AI", "https://rsshub.app/wechat/mp/gh_0b8b4b4b4b4b", "rss", "wechat", "zh", 2, "pending", "微信公众号：阿里云 AI 产品动态"),

    # ── 算力 / 基础设施 ──
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "rss", "infra", "en", 4, "active", "Hugging Face 官方博客（模型/数据集/Infra）"),
    ("Modal Blog", "https://modal.com/blog/feed.xml", "rss", "infra", "en", 3, "pending", "Modal：Serverless GPU 平台"),
    ("Latent Space", "https://www.latent.space/feed", "rss", "infra", "en", 3, "pending", "Latent Space：AI Infra 深度播客/文章"),
]
