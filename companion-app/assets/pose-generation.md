# 拎起、坐下、悬挂与探头素材

2026-10-15，内置image_gen生成。原始透明PNG复制到web/sakiko-pose-atlas.png，未使用离线绘图替代图像生成。浏览器按四个实际区域取图并绘制；生成结果两列的上下间隔不同，因此运行时左列在52%高度、右列在58%高度分割，避免坐姿鞋子被截断。与Cubism Live2D模型明确区分。

原始输出：C:/Users/16408/.codex/generated_images/01a1392d-c333-7e62-8eee-5c4363c9d0e0/exec-b1730b98-8c5c-49a9-8858-45af2377ae58.png。
参考图：web/sakiko-chibi-atlas.png（此前生成的同角色表情图集）。

## 完整提示词

Use case: stylized-concept. Asset type: transparent four-pose chibi sprite atlas for a playful desktop pet.
Reference: use the attached Sakiko sheet as a character identity/style reference ONLY. Same Toyokawa Sakiko from BanG Dream: long pale periwinkle blue twin tails, black small hair ribbons, amber eyes, cream modest long-sleeve blouse with thin black neck bow, gray plaid knee-length skirt, white socks and black Mary Janes. All ages, fully clothed, no upskirt view. Preserve cute fine-lined anime cel-shading, oversized head and tiny 2.5-head-tall body. Each head approximately the same size across poses.
Layout: square PNG, strict 2x2 equal square cells, genuine alpha transparency, no text, no labels, no frames, no props/platform drawn, no human hand/cursor drawn, no shadow or background. Keep each pose entirely inside its own cell with 10% padding. Same character only, one pose per cell:
TOP LEFT — LIFTED BY BACK COLLAR: three-quarter facing viewer, blouse fabric gathered into a small visible pinched fold just behind the nape between shoulder blades as if an invisible mouse is picking up that pinch. Tiny body hanging freely, arms and legs relaxed dangling, hair hanging with gravity, feet clear of ground, mildly surprised/bashful face. No hand reaching in, no rope. No changes to modest clothing.
TOP RIGHT — SITTING ON AN INVISIBLE LEDGE: front-three-quarter view, seated with knees together, hands resting neatly by hips on invisible ledge, lower legs hanging forward/down, gentle proud little smile. Clear bent seated silhouette distinct from standing. Do not draw ledge.
BOTTOM LEFT — HANGING FROM AN INVISIBLE LEDGE ABOVE: BOTH ARMS RAISED straight up, BOTH HANDS gripping at the SAME HORIZONTAL line slightly above head, body and legs dangling below, determined but adorable expression. No visible bar, wall, ledge or object.
BOTTOM RIGHT — PEEKING OVER AN INVISIBLE LEDGE: head and two small hands ONLY, both hands at same horizontal line below chin, looking curiously forward, the rest of body deliberately not drawn as if hidden behind a UI card. No ledge drawn.
Make the poses clear and usable at 150px character size. No glowing effects, no hearts or speech balloons, no checkerboard, no watermark. Genuine transparent exterior.
