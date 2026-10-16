# Q版日常立绘来源

使用内置image_gen工具，以原sakiko-chibi-atlas.png为参考，生成新兄弟文件，不覆盖原图。已保存web/sakiko-daily-atlas-031.png。四个等格：左上真实背影、右上困倦、左下吃饭、右下耳机听歌；透明背景。集成时按alpha轮廓定位；仅站立姿势用新画，坐/挂/拎沿用已有专用姿势。

生成提示词摘要（非工具调用逐字日志；原始提示记录于本聊天image_gen调用）：exactly four full-body Toyokawa Sakiko chibi sprites in a precise 2x2 equal-cell transparent atlas, identical periwinkle long hair, black bows, golden eyes, cream blouse, black collar bow, grey plaid skirt, white socks and black Mary Jane shoes; 12% transparent margin. Top-left genuine rear view with no face; top-right sleepy; bottom-left rice bowl and spoon; bottom-right dark-blue over-ear headphones. No text/grid/borders/shadow. Match the original reference, crisp clean alpha edges.

第二次针对性编辑：保留四姿势、位置、服装、脸和真实背面，只清理发丝、裙边、鞋周围蓝/青/品红/白色镂空边缘噪点，不改变2x2布局、不裁切、不加文字，保持透明。图像工具仍产生少量细边色，未冒称所有边缘已精修。原生成文件留在.codex/generated_images，本项目引用的是复制件。

使用真实背面做180/220ms淡入淡出，不再用横向压扁或翻转正面冒充转身。11次/8秒/邻间隔0.8秒和15秒冷却逻辑沿用已验证状态机。
