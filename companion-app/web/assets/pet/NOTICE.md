# 本机宠物资源与运行库

本目录用于用户提供的 GALMYGO 资源包在本机运行。没有执行角色卡、正则、HTML、作者 JavaScript 或 ZIP 中的可执行脚本。

- `live2d/010_*`：只导入祥子五套 Cubism 3 模型本体、贴图、物理、28表情和64动作引用。来源是用户 Downloads 中的 `01-GALMYGO2.5-基础28人与全部基础背景.galupdate` 的 `part-02.zip`。分卷 SHA256 与原清单一致；详细目录见 manifest.json。人物素材的版权和再分发许可没有从资源包中核实，不将其标记为 MIT，也没有对外发布素材。
- `vendor/pixi.min.js`：PixiJS 6.5.10，MIT，保留 `PIXI-LICENSE.txt`。
- `vendor/cubism4.min.js`：pixi-live2d-display 0.4.0，MIT，保留 `DISPLAY-LICENSE.txt`。该插件的 Cubism 4 适配器向后兼容这里的 Cubism 3 数据；菜单中的“原比例”仍保持原模型长宽比。
- `vendor/live2dcubismcore.min.js`：来自 Live2D 官方 Cubism SDK for Web 5 R4 ZIP。Core 是 Live2D 专有许可；保留 `CORE-LICENSE.md`、`CORE-RedistributableFiles.txt` 和原文件版权头，不将 Core 归入 MIT。许可信息：[Core许可](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)、[Framework开放许可](https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html)、[官方下载](https://www.live2d.com/en/sdk/download/web/)。
- `vendor/provenance.json`：实际下载来源、版本、SHA256；npm归档下载时核对 registry 的 SHA1 和 SHA512 integrity。没有运行 npm install 或包内生命周期脚本。

运行时依赖与人物素材均由本机静态服务器读取，不访问远程 CDN。默认 Q 版仍是本地精灵图与 Canvas 小动作，未声称为 Q 版 Live2D。原比例模型提供真实衣装、表情和模型动作；没有背面素材，也没有纸片翻转。

`qa-*.png` 是无账户信息、无模型API调用的本机浏览器夹具截图。
