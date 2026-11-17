# pawchive-dl

一个专注于 Pawchive 的命令行下载工具，可下载创作者页面或单篇帖子，支持关键词搜索、收藏创作者、归档跳过、日期和附件筛选，以及自定义输出模板。

默认输出模板：

```text
{service}/{creator_id}/{post_id}/{filename}
```

## 安装

需要 Python 3.11 或更高版本。

```bash
git clone https://github.com/yuxic9894/pawchive-dl.git
cd pawchive-dl
pip install .
```

## 使用

```bash
pawchive-dl --version
pawchive-dl "https://pawchive.pw/SERVICE/user/CREATOR_ID"
pawchive-dl "https://pawchive.pw/SERVICE/user/CREATOR_ID/post/POST_ID"
```

常用选项：

| 选项 | 说明 |
| --- | --- |
| `--path PATH` | 下载文件的根目录 |
| `--output [Type:]TEMPLATE` | 设置输出路径模板；可重复传入 |
| `--batch-file FILE` | 从文本文件逐行读取 URL，`#` 开头的行会忽略 |
| `--cookies FILE` | 加载 Pawchive cookies；可重复传入 |
| `--pawchive-login USERNAME PASSWORD` | 登录 Pawchive |
| `--favorite-creators-pawchive` | 下载已收藏创作者的帖子（需要登录） |
| `--archive FILE` | 记录已成功处理的帖子并跳过已记录帖子 |
| `--date [Type:]DATE` | 只下载指定日期的帖子，日期格式为 `YYYYMMDD` |
| `--datebefore [Type:]DATE` | 只下载指定日期或更早的帖子 |
| `--dateafter [Type:]DATE` | 只下载指定日期或更晚的帖子 |
| `--skip-extensions EXTs` | 跳过指定附件扩展名，以逗号分隔，不带点号 |
| `--skip-attachments` | 不下载帖子附件 |
| `--write-content` | 将帖子正文保存为 HTML 文件 |
| `--write-json` | 将帖子 API 响应保存为 JSON 文件 |
| `--write-links` | 提取正文中的 HTTP/HTTPS 链接，汇总保存为 Markdown 文件 |
| `--custom-template-variables FILE` | 从 JSON 文件加载自定义模板变量 |
| `--restrict-names` | 将输出文件名限制为 ASCII 字符 |
| `--no-tmp` | 直接写入目标文件，不使用 `.tmp` 临时文件 |

日期类型可选 `added`、`edited`、`published`，例如 `--date added:20250813`。未指定类型时按发布日期筛选。

## 创作者关键词搜索

在创作者 URL 后添加 `?q=关键词`，程序会将关键词传给 Pawchive API 分页查询：

```bash
pawchive-dl --path ~/Downloads/Pawchive \
  --output "{creator_name}/{filename}" \
  --skip-extensions "png,jpeg,jpg,gif" \
  "https://pawchive.pw/fanbox/user/73132618?q=becky"
```

关键词只应用于创作者页面；单篇帖子 URL 会直接下载该帖子。

## 输出模板

模板类型为 `attachments`、`content`、`json` 和 `links`。不写类型时，模板会应用于全部类型；明确指定类型的模板优先于通用模板。日期可以用 `strftime` 格式化，例如 `{published:%Y%m%d}`。

## 提取帖子正文链接

启用 `--write-links` 后，程序会从已获取的帖子正文 HTML 中提取 HTTP/HTTPS 超链接，并写入 Markdown 文件，不会额外请求帖子网页。同一创作者的帖子共用一个链接文件；每篇帖子以标题、Post ID、原帖 URL 和链接列表组成独立区块。重复处理同一帖子会更新原区块；成功解析出空链接时会移除该帖区块。

未设置 `--output` 时，默认路径为 `{service}/{creator_id}/links.md`：

```bash
pawchive-dl --path ~/Downloads/Pawchive --write-links \\
  "https://pawchive.pw/fanbox/user/73132618/post/123456"
```

如已设置通用 `--output`，链接文件会沿用它的目录模板，并用 `links.md` 作为 `{filename}`：

```bash
pawchive-dl --path ~/Downloads/Pawchive \\
  --output "{creator_name}/{filename}" \\
  --write-links "https://pawchive.pw/fanbox/user/73132618/post/123456"
```

也可以用 `links:` 单独指定链接文件路径；它优先于通用 `--output`：

```bash
pawchive-dl --path ~/Downloads/Pawchive \\
  --output "{creator_name}/{filename}" \\
  --output "links:{creator_name}/external-links.md" \\
  --write-links "https://pawchive.pw/fanbox/user/73132618/post/123456"
```

常用变量包括 `{service}`、`{creator_id}`、`{creator_name}`、`{post_id}`、`{post_title}`、`{filename}`、`{file_name}`、`{file_ext}`、`{server_filename}`、`{sha256}`、`{added}`、`{published}`、`{edited}`、`{index}` 和 `{attachments_count}`。

可以分别设置附件、正文和 JSON 文件的路径：

```bash
pawchive-dl --output "{service}/{creator_id}/{post_id}/{index}_{filename}" --output "content:{service}/{creator_id}/{post_id}/content.html" "https://pawchive.pw/patreon/user/12345/post/67890"
```

自定义变量可放在 JSON 文件中，值会作为 Python 表达式求值，也可以引用内置变量：

```json
{
  "titleTrunc": "'{post_title}'[:50]",
  "indexPlusOne": "{index} + 1"
}
```

使用 `--custom-template-variables FILE` 加载后，即可在模板中写 `{titleTrunc}` 或 `{indexPlusOne}`。

例如，为视频下载设置单独的文件名模板，并跳过常见图片和压缩文件：

```bash
pawchive-dl --path ~/Downloads/Pawchive \
  --output "{creator_name}/{filename}" \
  --skip-extensions "png,jpeg,jpg,gif,zip" \
  "https://pawchive.pw/fanbox/user/73132618?q=becky"
```


也可以一次传入多篇帖子 URL，并跳过视频以外的常见附件：

```bash
pawchive-dl --path ~/Downloads/Pawchive \
  --output "{creator_name}/{filename}" \
  --skip-extensions "mp4,gif,zip" \
  "https://pawchive.pw/patreon/user/2963401/post/153301414" \
  "https://pawchive.pw/patreon/user/2963401/post/157130329" \
  "https://pawchive.pw/patreon/user/2963401/post/157185380" \
  "https://pawchive.pw/patreon/user/2963401/post/161896325" \
  "https://pawchive.pw/patreon/user/2963401/post/162251503"
```

pawchive-dl --path ~/Downloads/Pawchive --output "{creator_name}/{filename}" --skip-extensions "png,PNG,jpeg,jpg,gif,zip,mp4" --write-links https://pawchive.pw/patreon/user/3295915