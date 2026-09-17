# Reddit 关键词采集器

这个项目通过 Reddit 官方 Data API 获取指定关键词最近一段时间内的帖子，并把帖子和评论保存到 SQLite。当前默认时间窗口是最近 7×24 小时，AI 分析暂未接入。

## 1. 创建 Reddit API 应用

登录 Reddit 后进入开发者应用页面，创建一个 `script` 类型应用，准备好：

- `client_id`
- `client_secret`
- 一个明确的 `user_agent`，例如 `keyword-monitor/0.1 by u/your_username`

不要把密钥提交到 Git。`.env` 已被 `.gitignore` 忽略。

## 2. 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```dotenv
REDDIT_CLIENT_ID=你的client_id
REDDIT_CLIENT_SECRET=你的client_secret
REDDIT_USER_AGENT=keyword-monitor/0.1 by u/你的用户名
DATABASE_PATH=data/reddit.db
```

## 3. 运行

搜索全站最近 7 天内包含关键词的帖子，并抓取每个帖子的全部可展开评论：

```bash
python main.py "人工智能" --verbose
```

只搜索某个 subreddit：

```bash
python main.py "python" --subreddit learnpython --post-limit 50
```

只抓取评论树当前已经返回的部分，不继续展开 `MoreComments`：

```bash
python main.py "python" --comment-more-limit 0
```

## 4. 数据表

- `posts`: 帖子正文、标题、作者、分数、subreddit、时间、链接等。
- `comments`: 评论正文、作者、父评论、层级、分数、时间等。
- `post_keywords`: 同一个帖子被多个关键词命中的关系。
- `crawl_runs`: 每次运行的状态、数量和错误信息。

帖子和评论都按 Reddit ID 做 upsert，重复运行不会产生重复记录；重复运行也会刷新分数、评论数和抓取时间。

## 5. 注意事项

Reddit 搜索本身有结果数量和 API 调用限制，`--post-limit` 是候选上限，不代表一定能拿到该时间窗口内的全部帖子。评论展开可能产生很多 API 请求，热门帖子尤其明显。生产环境建议按 subreddit 拆分查询、保存游标/运行状态并做限速和失败重试。

另外，使用 Reddit Data API 时需要遵守 Reddit 的 Data API Terms、开发者条款、隐私和内容删除要求；不能绕过 API 限制，也不能未经内容权利人明确许可把用户内容用于 AI 模型训练。

