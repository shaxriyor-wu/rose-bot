BOT_TOKEN = "8077819092:AAESe5YrG6R_y0jZ2uZuBaTxyebdDz10oxA"

FORBIDDEN_WORDS = [
    "Ahmoq","Am","Amcha","Befarosat","Blyat","Buvini ami","Cho'choq","Dalban","Dalbayob",
    "Dalbayop","Dnx","Dovdir","Ey qetoq","Foxisha","Fuck","Fuck you","Gandon","Gotalak",
    "Haromi","Hunasa","Iflos","Iplos","Isqirt","Jalab","Jalla","Jallab","Jallap","Jinni",
    "Jipiriq","Kispurush","Ko't","Kot","Kotinga","Koʻt","Lox","Manjalaqi","Maraz","Mol miyya",
    "Om","Onangni sikay","Onenei ami","Opangni omiga ske","Pasholak","Pidaraz","Pidr","Pipez",
    "Pizdes","Poxuy","Poxxuy","Pzdc","Pzds","Pzdss","Qanchiq","Qanciq","Qanjiq","Qetoq",
    "Qo'taq","Qotaqxor","Qoto","Qotoq","Qotoqbosh","Qo’toq","Seks","Sen qishloqlisan",
    "Sik","Sikaman","Sikay","Sikdim","Ske","Suchka","Suka","Tashoq","Tashshoq",
    "Tashshoq sho'rva","Tashshoq sho’rva","Tente","Xaromi","Ya yebal tebya","Yban","Ybat",
    "Yeban","Yebanutiy","Yiban","Zaybal","ahmoq","ahuel","am","ambaliq","amcha","aminga",
    "amingga ske","axmoq","basharenga qotogm","bich","bitch","ble","blet","bo'qidish",
    "bo'qkalla","boq","chmo","chumo","dabba","dalbayob","daun","dinnaxuy","fuck","fuck off",
    "fucking","gandon","garang","gay","gey","gnida","haromi","hunasa","idi naxuy","iflos","it",
    "itbet","jala","jala ble","jalaaap","jalab","jalap","jalla","jallap","ko't", "idinnahhuy", "yban", 
    "soska", "Itdan bogan", "apanngi skin", "ananggi skin", "ananggi ommi",
    "fucking","gandon","garang","gay","gey","gnida","haromi","hunasa","idi naxuy","iflos","it",
    "itbet","jala","jala ble","jalaaap","jalab","jalap","jalla","jallap","ko't","kot","lox",
    "mol","nedagon",
    "oʻl","p1zdes","pashol na xuy","pidaras","pidaraz","pidr","pizda","pizdes","qanjiq",
    "qo'toq","qo'toqbosh","qotaq","qoto","qotoq","qutoq","seks","seksi baby","sex",
    "sexy woman","shavqatsiz","sikay","sike","sikish","siktim","sikvoti","skay","ske",
    "skey","suchka","suka","sukka","tashsho","tupoy","tvar","tvariddin","wtf","xaromi",
    "xuyeplet","xuyesos","xuyila","yban","yeban","yebanashka","yebat","yebbat","yeblan",
    "yebnu","yebu","yetim","yetm","yiban","yibanat", "bla", "blaat", "blat", "bld", "blyad", "blyat", "blya",'kot', 'chort', 'dalbay','skin','qotak', 'skdng', 
    'skivarding','qotakm','qotogm','qotak','qotogm','soska','itdan bogan','apanngi skin','ananggi skin','ananggi ommi'
]

PUNISHMENT_DURATIONS = [60, 300, 1800, 3600] 


BLOCKED_MESSAGE_TEMPLATE = (
    "❗️ Siz {count}-marta qoida buzdingiz.\n"
    "⏳ Siz {duration} ga bloklandingiz."
)

GROUP_NOTIFICATION_TEMPLATE = (
    "❗️ <a href='tg://user?id={user_id}'>{user_name}</a> qoida buzdi!\n"
    "📊 24 soat ichida: {daily_count}-marta\n"
    "📈 Jami: {total_count}-marta\n"
    "⏰ Blok vaqti: {duration}\n"
    "🕐 Qachongacha: {until_time}"
)

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds} soniya"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} daqiqa"
    else:
        hours = seconds // 3600
        return f"{hours} soat"

def format_until_time(seconds):
    """Qachongacha bloklanganligini ko'rsatadi"""
    from datetime import datetime, timedelta
    until = datetime.now() + timedelta(seconds=seconds)
    return until.strftime("%H:%M:%S")