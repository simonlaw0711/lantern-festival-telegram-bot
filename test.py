import random

poem_lines = [
            "元宵佳节到，请你吃元宵，香甜满心间，新春人更俏。",
            "正月十五良宵到，花灯吐艳把春报；一年初望明月照，汤圆滚烫闹良宵。",
            "元宵喜庆乐盈盈，大伙开心闹元宵，大街小巷人气旺 ，开开心心过元宵！",
            "元宵佳节明月圆，人间欢乐丰收年，花灯照亮好前景，日子幸福比蜜甜，健康快乐身体好，万事如意随心愿。",
            "元宵节来吃汤圆，吃碗汤圆心甜甜；幸福汤圆一入口，健康快乐常陪伴；爱情汤圆一入口，心如细丝甜如蜜；金钱汤圆一入口，财源滚滚斩不断！",
            "天上繁星晶晶亮，地上彩灯换色彩；天上明月寄相思，地上汤圆寄团圆；又逢一年元宵节，温馨祝福送心田；健康吉祥送给你，愿你梦想都实现。",
            "月儿圆圆挂枝头，元宵圆圆入你口，又是元宵佳节到，吃颗元宵开口笑，笑笑烦恼都跑掉，一生好运围你绕，事事顺利真美妙，元宵佳节乐逍遥！",
            "正月十五赏花灯，祝你心情亮如灯；正月十五吃汤圆，祝你阖家喜团圆；正月十五元宵香，祝你身体更健康；正月十五喜连连，祝你万事皆吉祥。",
            "正月十五闹花灯，焰火惊艳添福运；舞龙舞狮普天庆，且看且叹不须停；热火朝天贺元宵，万家团圆福气绕；祥瑞扑面跟你跑，幸福日子更美好！",
            "正月十五月儿圆，美好祝福在耳边；正月十五元宵甜，祝你今年更有钱；正月十五汤圆香，祝你身体更健康；正月十五乐团圆，祝你元宵乐连连！",
            "正月十五月儿圆，真诚祝福送身边；正月十五元宵甜，祝你龙年更有钱；正月十五展笑颜，快乐长久幸福绵；正月十五享团圆，祝你吉祥在龙年！",
            "车如流水马如龙，相约赏灯乐融融；金狮涌动舞不停，猜中灯谜笑盈盈；皎皎明月泻清辉，颗颗汤圆情意随；元宵佳节已然到，愿你开怀乐淘淘。",
            "春风阵阵佳节到，元宵灯会真热闹；四面八方人如潮，欢声笑语声声高；亲朋好友祝福绕，开开心心活到老；祝你佳节好运罩，万事顺利人欢笑！",
            "鱼跃龙门好有福，元宵佳节早送福；大福小福全家福，有福享福处处福；知福来福有祝福，清福鸿福添幸福；接福纳福年年福，守福祈福岁岁福！",
            "元宵佳节明月升，嫦娥曼舞看清影，元宵香从圆月来，高歌一曲赏美景，亲友团圆叙旧情，一缕相思圆月中，团圆之夜思绪浓，共用快乐互叮咛。",
            "一元复苏大地春，正月十五闹元宵。圆月高照星空灿，灯火辉煌闹春年。万家灯火歌声扬，团团圆圆品汤圆，其乐融融笑声甜，幸福滋味香飘然。",
            "元宵圆圆盘中盛，举家投著来品尝。颗颗润滑甜如蜜，团圆之情入心底。彩灯纷纷空中挂，亲友相约赏灯忙。灯火通明好年景，万千喜悦心中放。",
            "唢呐声声人欢笑，张灯结彩闹元宵。明月花灯两相照，龙狮飞舞热情高。烟花爆竹绽笑颜，剪纸窗花美无边。一碗汤圆香又甜，万千祝福润心田。",
            "点点元宵似珍珠，用心品尝香无数。一个元宵千般情，愿你天天好心情。展展花灯美无边，流连忘返人群间。一个花灯万般愿，愿你生活比蜜甜。",
            "元宵佳节闹花灯，一份祝福藏其中。明月皎皎人团圆，汤圆香甜爱情甜。红灯高照事业旺，美酒醇厚阖家康。愿你元宵乐连连，开心幸福绽笑颜。",
            "正月十五月儿圆，元宵佳节喜庆多，心情愉快朋友多，身体健康快乐多，财源滚滚钞票多，全家团圆幸福多，年年吉祥如意多，岁岁平安多好事！",
            "杨柳轻扬春意早，十里长街闹元宵。扭动腰肢挑花灯，耄耋童子齐欢笑。糯米揉团蜜馅包，团团圆圆吃到饱。叙过家常侃大山，大家一起乐元宵。"
        ]


poem = random.choice(poem_lines)
# poem = "正月十五良宵到，花灯吐艳把春报；一年初望明月照，汤圆滚烫闹良宵。"

def format_poem_vertically_with_side_decorations_and_spacing(poem, spacing=1):
    # Define punctuation
    punctuation = "，、。！？；：「」『』（）《》【】"
    
    # Find the length of the first line before any punctuation
    first_line_length = next((i for i, char in enumerate(poem) if char in punctuation), len(poem))
    
    # Calculate column_height
    column_height = first_line_length
    
    # Remove punctuation
    for p in punctuation:
        poem = poem.replace(p, "")
    
    # Calculate the number of characters and columns
    num_chars = len(poem)
    num_columns = -(-num_chars // column_height)
    
    # Initialize the grid with full-width spaces
    grid = [['\u3000' for _ in range(num_columns)] for _ in range(column_height)]
    
    # Fill the grid with characters
    for i, char in enumerate(poem):
        col = num_columns - 1 - i // column_height
        row = i % column_height
        grid[row][col] = char
    
    # Add spacing between lines and add lanterns to the left and right
    space = '\u3000' * spacing  # Use full-width space for spacing
    formatted_poem_lines_with_decor = [
        '🏮' + space.join(row) + '🏮' for row in grid
    ]
    
    # Combine everything into one string
    formatted_poem_with_side_decor = '\n'.join(formatted_poem_lines_with_decor)
    
    return formatted_poem_with_side_decor

# Adjust the spacing parameter as desired; 2 for example adds more space
formatted_poem = format_poem_vertically_with_side_decorations_and_spacing(poem, spacing=2)
print(formatted_poem)
