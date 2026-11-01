# kemono-dl

一个用于下载 Kemono、Coomer 和 Pawchive 内容的工具。

> ⚠️ Kemono 和 Coomer 的文件服务器已失效，尝试从它们下载文件会失败。`kemono-dl` 已更新为支持 Pawchive；Pawchive 是使用相同 API 结构的 Kemono 替代站点。

> ⚠️ 自 `2025.08.13` 版本起，`kemono-dl` 不再与旧版本完全兼容。若希望使用旧版的默认下载路径模板，可手动指定：
>
> ```bash
> --output "{service}/{creator_name} [{creator_id}]/[{published:%Y%m%d}] [{post_id}] {post_title}/{index}_{filename}"
> ```
>
> 此模板与旧行为非常接近；但旧版本会截断超过 255 个字符的路径和文件名，新版本没有完全复刻该逻辑。多数情况下该模板仍可正常工作。

## 安装

1. **安装 Python**
   确保已安装 Python 3.11 或更高版本，并且可在系统 `PATH` 中找到。

2. **下载最新版本**
   下载[最新版本](https://github.com/AplhaSlayer1964/kemono-dl/releases/latest)的源码并解压。

3. **使用 pip 安装**
   打开终端，进入解压后项目的根目录（即包含 `pyproject.toml` 的目录），然后运行：

   ```bash
   pip install .
   ```

4. **运行 kemono-dl**

   ```bash
   kemono-dl --version
   kemono-dl "https://pawchive.pw/SERVICE/user/CREATOR_ID"
   kemono-dl "https://pawchive.pw/SERVICE/user/CREATOR_ID/post/POST_ID"
   ```

> **提示：** 更新时，请使用最新版源码重复第 2 和第 3 步。

## 命令行选项

| 选项                                   | 说明                                                                                              |
| ------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `--version`                          | 输出版本号后退出。                                                                                       |
| `--path PATH`                        | 设置下载文件的根目录。                                                                                     |
| `--output [Type:]TEMPLATE(s)`        | 设置输出文件路径模板。详情见[输出模板](#输出模板)。                                                                    |
| `--batch-file FILE`                  | 从文件读取 URL，每行一个 URL。                                                                             |
| `--cookies FILEs`                    | 提供 Kemono/Coomer 的 Cookies 文件；`--favorite-creators-coomer` 和 `--favorite-creators-kemono` 需要此项。 |
| `--coomer-login USERNAME PASSWORD`   | 使用 Coomer 用户名和密码登录。                                                                             |
| `--kemono-login USERNAME PASSWORD`   | 使用 Kemono 用户名和密码登录。                                                                             |
| `--pawchive-login USERNAME PASSWORD` | 使用 Pawchive 用户名和密码登录。                                                                           |
| `--favorite-creators-coomer`         | 下载 Coomer 中所有收藏的创作者。                                                                            |
| `--favorite-creators-kemono`         | 下载 Kemono 中所有收藏的创作者。                                                                            |
| `--favorite-creators-pawchive`       | 下载 Pawchive 中所有收藏的创作者。                                                                          |
| `--restrict-names`                   | 将输出文件名限制为 ASCII 字符。                                                                             |
| `--custom-template-variables FILE`   | 指向包含自定义模板变量的 JSON 文件。                                                                           |
| `--date [Type:]DATE`                 | 仅下载指定日期发布的帖子；格式为 `YYYYMMDD`。**（注 1）**                                                           |
| `--datebefore [Type:]DATE`           | 仅下载指定日期或更早发布的帖子；格式为 `YYYYMMDD`。**（注 1）**                                                        |
| `--dateafter [Type:]DATE`            | 仅下载指定日期或更晚发布的帖子；格式为 `YYYYMMDD`。**（注 1）**                                                        |
| `--skip-extensions EXTs`             | 跳过指定扩展名的文件，使用逗号分隔，且不要包含点号；检查的是原始文件名的扩展名。                                                        |
| `--skip-attachments`                 | 跳过下载帖子的附件。                                                                                      |
| `--write-content`                    | 将帖子正文写入文件。                                                                                      |
| `--write-json`                       | 将帖子 API 的 JSON 响应写入文件。                                                                          |
| `--no-tmp`                           | 不使用 `.tmp` 临时文件，直接写入目标文件。                                                                       |
| `--archive FILE`                     | 指定已下载帖子记录文件；已记录的帖子会被跳过。                                                                         |

> **注 1：** 可按不同日期类型筛选：`"added:YYYYMMDD"`、`"edited:YYYYMMDD"`、`"published:YYYYMMDD"`。未指定类型时，默认按发布日期筛选。

### 按关键词搜索创作者的帖子

对于 Pawchive 创作者页，可在 URL 后添加 `?q=关键词`，只下载标题或内容与关键词匹配的帖子。该关键词会在获取每一页帖子时传给 Pawchive API。

```bash
kemono-dl --path ~/Downloads/Pawchive \
  --output "{creator_name}/{filename}" \
  --skip-extensions "png,jpeg,jpg,gif" \
  "https://pawchive.pw/fanbox/user/73132618?q=becky"
```

`q` 仅适用于创作者 URL；当 URL 指向单篇帖子（包含 `/post/POST_ID`）时，程序会直接下载该帖子，不使用搜索参数。

## 输出模板

### 输出模板类型

输出模板类型可为不同类别的输出定义不同的文件路径格式。默认情况下，所有类型均使用：`"{service}/{creator_id}/{post_id}/{filename}"`。

若没有指定类型，传入的模板会应用于全部输出类型。

| 类型              | 说明               |
| --------------- | ---------------- |
| `"attachments"` | 保存帖子附件的输出模板。     |
| `"content"`     | 保存帖子正文的输出模板。     |
| `"json"`        | 保存帖子 JSON 的输出模板。 |

#### 输出模板类型示例

```bash
kemono-dl --output "{service}/{creator_id}/{post_id}/{index}_{filename}" --output "content:{service}/{creator_id}/{post_id}/{filename}" "https://kemono.cr/patreon/user/12345/post/67890"
patreon/12345/67890/0_attachment.png
patreon/12345/67890/1_attachment.png
patreon/12345/67890/content.html
```

### 输出模板变量

| 变量                    | 说明                                                                                                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `{service}`           | 服务名称。                                                                                                                                                                    |
| `{creator_id}`        | 创作者 ID。                                                                                                                                                                  |
| `{creator_name}`      | 创作者名称。                                                                                                                                                                   |
| `{post_id}`           | 帖子 ID。                                                                                                                                                                   |
| `{post_title}`        | 帖子标题。                                                                                                                                                                    |
| `{server_filename}`   | 服务器文件名，包含扩展名。                                                                                                                                                            |
| `{server_file_name}`  | 服务器文件名，不含扩展名；等同于 `{sha256}`。                                                                                                                                             |
| `{server_file_ext}`   | 服务器文件扩展名，不含 `.`；可能与 `{file_ext}` 不同。                                                                                                                                     |
| `{filename}`          | 原始文件名，包含扩展名。**（注 4）**                                                                                                                                                    |
| `{file_name}`         | 原始文件名，不含扩展名。                                                                                                                                                             |
| `{file_ext}`          | 原始文件扩展名，不含 `.`；可能与 `{server_file_ext}` 不同。                                                                                                                               |
| `{sha256}`            | 由 Kemono/Coomer 生成的文件 SHA-256 哈希值。                                                                                                                                       |
| `{added}`             | 帖子被加入 Kemono/Coomer 的日期时间。可使用 `{added:FORMAT}` 格式化；请参阅 [strftime 格式代码](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes)。**（注 1、2、3）** |
| `{published}`         | 帖子发布到原服务的日期时间。可使用 `{published:FORMAT}` 格式化。**（注 1、2、3）**                                                                                                                 |
| `{edited}`            | 帖子被编辑的日期时间。可使用 `{edited:FORMAT}` 格式化。**（注 1、2、3）**                                                                                                                       |
| `{index}`             | 帖子主文件和附件的顺序编号，从 0 开始。**（注 5）**                                                                                                                                           |
| `{attachments_count}` | 帖子的附件总数，包含帖子主文件。                                                                                                                                                         |

> **注 1：** 若解析 `{added}`、`{published}` 或 `{edited}` 时出错，会默认使用 `0001 年 1 月 1 日`；帖子中相应值为 `Null` 时也一样。
>
> **注 2：** Fanbox 服务的 `{added}` 始终为 `Null`，因此其值总会是 `0001 年 1 月 1 日`。
>
> **注 3：** 在 Windows 批处理文件中，必须将 `%` 写成 `%%`。
>
> **注 4：** `{filename}` 不保证唯一；建议使用 `{server_filename}` 或 `{sha256}` 来确保唯一性。
>
> **注 5：** 若帖子有主文件，它的编号为 0，其他附件依次在后。

#### 输出模板示例

```bash
kemono-dl --output "{service}/{creator_id}/{post_id}/{filename}" "https://kemono.cr/patreon/user/12345/post/67890"
patreon/12345/67890/attachment.png

kemono-dl --output "{service}/{creator_id}/{post_id}/{server_filename}" "https://kemono.cr/patreon/user/12345/post/67890"
patreon/12345/67890/wm54swsglbfs4583qzp7u880tmglvdqzeg6vqni12s6ywfsk3l8afp5ycfwo2hw4.png
# wm54swsglbfs4583qzp7u880tmglvdqzeg6vqni12s6ywfsk3l8afp5ycfwo2hw4 是由 Kemono/Coomer 生成的文件 SHA-256 哈希值

kemono-dl --output "{service}/{creator_id}/{post_id}_{file_name}_{sha256}.{ext}" "https://kemono.cr/patreon/user/12345/post/67890"
patreon/12345/67890_attachment_wm54swsglbfs4583qzp7u880tmglvdqzeg6vqni12s6ywfsk3l8afp5ycfwo2hw4.png

kemono-dl --output "{service}/{creator_id}/[{published:%Y-%m-%d %H-%M-%S}]_{post_id}/{filename}" "https://kemono.cr/patreon/user/12345/post/67890"
patreon/12345/[2025-08-13 00-00-00]_67890/attachment.png # 此帖子发布于 2025 年 8 月 13 日 00:00:00
```

#### 自定义模板变量

你可以在 JSON 文件中定义自己的模板变量；其值会作为 Python 表达式求值。自定义变量也可以使用 `{...}` 语法引用内置模板变量。

```json
{
   "titleTrunc": "'{post_title}'[:50]",
   "titleNoDogs": "'{post_title}'.replace('dog', 'cat')",
   "indexPlusOne": "{index} + 1",
   "indexPlusOneZfilled": "str({index} + 1).zfill(len(str({attachments_count})))"
}
```

在输出模板中，将它们和默认变量一样使用即可，例如 `{titleTrunc}`。


### 常用模版
```json
kemono-dl --path ~/Downloads/Pawchive --output "{creator_name}/{filename}" --skip-extensions "png,jpeg,jpg,gif" "https://pawchive.pw/fanbox/user/73132618?q=becky"
```

## 原项目

本项目基于 [AlphaSlayer1964/kemono-dl](https://github.com/AlphaSlayer1964/kemono-dl) 修改。
