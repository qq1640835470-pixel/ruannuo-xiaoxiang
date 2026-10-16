# 43ca7c7a · 音乐与工具布局 0.3.3

## 已完成
- 工具对话框分为首页与音乐子页；首页只保留原有同窗浏览器表单及音乐入口，音乐页保留网易云扫码/歌单/搜索、本地文件、音频控件、队列。通过既有 DOM 移动构建，无需修改 index.html。
- 音乐气泡单击展开、再次点击收起；独立“选歌 / 搜索”进入音乐子页。增加关闭按钮、音乐页“显示宠物音乐气泡”与“暂停时隐藏气泡”，偏好仅本机 localStorage。默认暂停显示“已暂停”，控件显示“播放”。
- 气泡使用视口内候选矩形定位，优先避开 #pet-bubble、.pet-controls、.pet-mode-panel[open]、.pet-menu、设置抽屉；狭窄视口允许内部滚动。空间完全不足时只能选择重叠最少的位置，未声称任意窗口尺寸零重叠。
- 正文/表单/说明恢复系统字体；标题可用圆润字体。工具说明与设置主标签 15px、设置次要说明 14px；无新增口号。
- “聊聊这首歌”仅用户点击调用 POST /api/music/commentary {title,artist}；展示返回 text，并以 xy:music-commentary 事件发送完整 {text,source,model}。请求中禁用重复点击，无自动评论。后端由主代理提供。
- 网易云账号读取从打开工具首页改为进入音乐子页触发；现有凭据/API未改。

## 验证
- node --check web/workspace-tools.js / web/netease-player.js / web/music-pet.js 通过。
- node test_music_v031.js 通过：本地/远程切换、搜索追加、暂停/继续、上下首、blob URL回收；旧DOM夹具已适配子页与新二击行为。
- node test_music_layout_v033.cjs 通过：真实本机Edge无头加载本项目HTML/CSS，使用本地拦截API验证首页/音乐往返、远程队列与暂停、气泡二击收起/选歌、手动评论请求/事件、关闭/显示/暂停隐藏偏好、1280×800/420×650/320×480边界及对话矩形避让、系统字体、无JS异常。全部API为夹具，无外部付费调用，不接触密钥。

## 改动文件
web/workspace-tools.js、web/netease-player.js、web/music-pet.js、web/music-pet.css、web/experience.css、test_music_v031.js、test_music_layout_v033.cjs。

## 整合注意
- 未改 index.html、companion.js、Live2D、app.js、server.py。
- 前端API夹具通过不等于真实模型评论验收；真实评论后端由主代理完成。
- 主代理统一更新 continuation.md 与 checkpoint，避免多个代理并发覆盖。
- 本轮未发生真实模型切换。
