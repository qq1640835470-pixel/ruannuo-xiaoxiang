# 小祥动态2D素材生成记录

日期：2026-10-15。使用内置 image_gen，透明背景，官方既有立绘仅作为外观参考。生成四表情图集，保持完整原始PNG，不进行离线涂改。运行时Canvas读取每格透明边界、对齐并绘制，完成眨眼、轻摆与表情切换。这是 sprite2d 渲染，不是 Cubism Live2D，也没有生成 moc/moc3 模型。

项目素材：web/sakiko-chibi-atlas.png。
原输出：C:/Users/16408/.codex/generated_images/01a1392d-c333-7e62-8eee-5c4363c9d0e0/exec-e7a65fde-638e-4487-ba99-68ee25ee28c2.png。
外观参考：D:/StudyLifePlan/artifacts/bandori-rolecards/sakiko.png。

## 最终生成提示

Use case: stylized-concept.
Asset type: transparent sprite atlas for a small interactive desktop chibi character, NOT a UI screenshot.
Reference image: use the attached official Toyokawa Sakiko art ONLY as an appearance reference. Draw new adorable soft polished anime chibi Toyokawa Sakiko (丰川祥子) from BanG Dream: pale periwinkle blue long twin tails, small black hair ribbons, amber-gold eyes, cream white blouse with thin black ribbon, muted gray plaid skirt, white socks and black Mary Jane shoes. Fully dressed, all ages. 2.5 heads tall, oversized cute head, tiny elegant body, hands held neatly together, front facing. Clean fine ink, soft cel shading, very legible at 150px tall. No pixel art.
CRITICAL layout: a perfectly aligned 2 by 2 sprite sheet on genuine alpha transparency. Four EQUAL cells, no gutters, no dividers, no text. In EVERY cell the SAME full-body character, SAME identical pose, SAME silhouette, SAME clothing, SAME head angle and size and exact pixel registration. Character fits fully within central 80% of each cell, feet at 94% cell height, top of head at 6%. Only the facial expression changes:
TOP LEFT: calm small gentle smile, eyes OPEN.
TOP RIGHT: same gentle smile, eyes completely CLOSED for a blink.
BOTTOM LEFT: bashful softly blushing, eyes OPEN, small shy smile, same body and pose.
BOTTOM RIGHT: slightly proud / mildly pouting but warm, eyes OPEN, tiny pout, same body and pose.
No shadows outside the character, no floating effects or decorations, no background, no checkerboard, no badges, no watermark, no labels. Use an overall square atlas with four identical square cells.
