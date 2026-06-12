path = 'app/src/main/java/com/psikochat/app/ui/home/WellnessDashboardScreen.kt'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''                                            val maxVal = sections.dailyTrend.maxOfOrNull { it.totalCount } ?: 1
                                            Canvas(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .height(100.dp)
                                            ) {
                                                val width = size.width
                                                val height = size.height
                                                val spacing = width / (sections.dailyTrend.size - 1).coerceAtLeast(1)

                                                val path = Path()
                                                sections.dailyTrend.forEachIndexed { i, item ->
                                                    val x = i * spacing
                                                    val y = height - (item.totalCount.toFloat() / maxVal.toFloat() * height * 0.8f)

                                                    if (i == 0) {
                                                        path.moveTo(x, y)
                                                    } else {
                                                        path.lineTo(x, y)
                                                    }
                                                    drawCircle(
                                                        color = LoginButton,
                                                        radius = 4.dp.toPx(),
                                                        center = androidx.compose.ui.geometry.Offset(x, y)
                                                    )
                                                }

                                                drawPath(
                                                    path = path,
                                                    color = LoginButton,
                                                    style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
                                                )
                                            }'''

new = '''                                            val maxVal = sections.dailyTrend.maxOfOrNull { it.totalCount } ?: 1
                                            // LoginButton @Composable property -- Canvas DrawScope disinda al
                                            val chartLineColor = LoginButton
                                            Canvas(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .height(100.dp)
                                            ) {
                                                val width = size.width
                                                val height = size.height
                                                val spacing = width / (sections.dailyTrend.size - 1).coerceAtLeast(1)

                                                val path = Path()
                                                sections.dailyTrend.forEachIndexed { i, item ->
                                                    val x = i * spacing
                                                    val y = height - (item.totalCount.toFloat() / maxVal.toFloat() * height * 0.8f)

                                                    if (i == 0) {
                                                        path.moveTo(x, y)
                                                    } else {
                                                        path.lineTo(x, y)
                                                    }
                                                    drawCircle(
                                                        color = chartLineColor,
                                                        radius = 4.dp.toPx(),
                                                        center = androidx.compose.ui.geometry.Offset(x, y)
                                                    )
                                                }

                                                drawPath(
                                                    path = path,
                                                    color = chartLineColor,
                                                    style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
                                                )
                                            }'''

if old not in content:
    print('ERROR: Target not found!')
    # Print around line 525
    lines = content.splitlines()
    for i, line in enumerate(lines[520:560], start=521):
        print(f'{i}: {repr(line[:80])}')
else:
    content2 = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content2)
    print('OK: Canvas color fix applied.')
