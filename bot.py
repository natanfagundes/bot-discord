import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import datetime
import requests
import sympy as sp  # type: ignore
import shutil

# Token do bot (substitua pelo seu token real)
TOKEN = "COLOQUE SEU TOKEN AQ"

if not TOKEN:
    raise ValueError("O token do Discord está vazio ou não foi fornecido!")

# Configuração de intents para permitir leitura de mensagens
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Dicionários para gerenciar filas, músicas atuais e modo loop
filas_musicas = {}  # Fila de músicas por servidor
musica_atual = {}   # Música atual por servidor
modo_loop = {}      # Estado do loop por servidor

# Função para encontrar o caminho do FFmpeg
def obter_caminho_ffmpeg():
    return shutil.which("ffmpeg") or "C:\\Users\\natan\\Desktop\\dist_v2\\ffmpeg.exe"  # Ajuste o caminho se necessário

caminho_ffmpeg = obter_caminho_ffmpeg()

# Função chamada após o término de uma música
def apos_tocar(erro, ctx):
    if erro:
        print(f"Erro ao tocar música: {erro}")
    # Agenda a verificação da fila no loop de eventos
    bot.loop.create_task(verificar_fila(ctx))

# Função para tocar a próxima música da fila
async def verificar_fila(ctx):
    id_servidor = ctx.guild.id
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        return

    if id_servidor in filas_musicas and filas_musicas[id_servidor]:
        proxima_musica = filas_musicas[id_servidor][0]
        if modo_loop.get(id_servidor, False):  # Repete a música atual se o loop estiver ativo
            url = musica_atual[id_servidor]["url"]
            titulo = musica_atual[id_servidor]["titulo"]
        else:
            proxima_musica = filas_musicas[id_servidor].pop(0)
            url = proxima_musica["url"]
            titulo = proxima_musica["titulo"]
            musica_atual[id_servidor] = {"url": url, "titulo": titulo}

        print(f"Tocando: {titulo} (URL: {url})")
        opcoes_ffmpeg = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -loglevel panic"
        }
        try:
            audio = discord.FFmpegPCMAudio(url, executable=caminho_ffmpeg, **opcoes_ffmpeg)
            ctx.voice_client.play(audio, after=lambda e: apos_tocar(e, ctx))
            embed = discord.Embed(title="🎵 Tocando Agora", description=f"**{titulo}**", color=discord.Color.blue())
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Erro ao tocar música: {str(e)}")
            embed = discord.Embed(description=f"Erro ao tocar {titulo}: {str(e)}", color=discord.Color.red())
            await ctx.send(embed=embed)
    else:
        musica_atual.pop(id_servidor, None)

# Verifica se o canal de voz está vazio
async def verificar_canal_voz(ctx):
    while ctx.voice_client and ctx.voice_client.is_connected():
        if len(ctx.voice_client.channel.members) <= 1:  # Apenas o bot
            await ctx.voice_client.disconnect()
            embed = discord.Embed(description="Saí do canal de voz porque está vazio! 👋", color=discord.Color.orange())
            await ctx.send(embed=embed)
            return
        await asyncio.sleep(60)  # Verifica a cada 60 segundos

# Comando para tocar música
@bot.command(name="p")
async def tocar(ctx, *, pesquisa: str):
    try:
        if not ctx.author.voice:
            embed = discord.Embed(description="Você precisa estar em um canal de voz!", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        canal = ctx.author.voice.channel
        if not ctx.voice_client:
            await canal.connect()
        elif ctx.voice_client.channel != canal:
            await ctx.voice_client.move_to(canal)

        cliente_voz = ctx.voice_client
        if not cliente_voz.is_connected():
            embed = discord.Embed(description="Não consegui conectar ao canal de voz!", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        opcoes_ydl = {
            "format": "bestaudio/best",
            "default_search": "auto",
            "noplaylist": False,
            "quiet": True,
        }

        with youtube_dl.YoutubeDL(opcoes_ydl) as ydl:
            info = ydl.extract_info(pesquisa, download=False)
            id_servidor = ctx.guild.id
            if id_servidor not in filas_musicas:
                filas_musicas[id_servidor] = []

            if "entries" in info:  # Playlist
                musicas = info["entries"]
                for musica in musicas:
                    filas_musicas[id_servidor].append({"url": musica["url"], "titulo": musica["title"]})
                embed = discord.Embed(title="📜 Playlist Adicionada", description=f"{len(musicas)} músicas adicionadas à fila!", color=discord.Color.blue())
                await ctx.send(embed=embed)
            else:  # Música única
                url = info["url"]
                titulo = info["title"]
                filas_musicas[id_servidor].append({"url": url, "titulo": titulo})
                embed = discord.Embed(title="🎶 Música Adicionada", description=f"**{titulo}** foi adicionado à fila.", color=discord.Color.blue())
                await ctx.send(embed=embed)

            if not cliente_voz.is_playing() and not cliente_voz.is_paused():
                await verificar_fila(ctx)

    except Exception as e:
        embed = discord.Embed(title="❌ Erro", description=f"Deu um erro: {str(e)}", color=discord.Color.red())
        await ctx.send(embed=embed)
        print(f"Erro no comando tocar: {str(e)}")

# Comando para pular música
@bot.command(name="skip")
async def pular(ctx):
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        embed = discord.Embed(description="⏭ Música pulada! Tocando a próxima...", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="❌ Não tem música tocando agora.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para mostrar a fila
@bot.command(name="queue")
async def fila(ctx):
    id_servidor = ctx.guild.id
    if id_servidor in filas_musicas and filas_musicas[id_servidor]:
        lista_fila = "\n".join([f"{i+1}. {musica['titulo']}" for i, musica in enumerate(filas_musicas[id_servidor])])
        embed = discord.Embed(title="📜 Fila de Músicas", description=lista_fila, color=discord.Color.purple())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="A fila está vazia!", color=discord.Color.orange())
        await ctx.send(embed=embed)

# Comando para pausar música
@bot.command(name="pause")
async def pausar(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        embed = discord.Embed(description="⏸ Música pausada.", color=discord.Color.yellow())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="❌ Não tem música tocando agora.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para retomar música
@bot.command(name="resume")
async def continuar(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        embed = discord.Embed(description="▶ Música retomada.", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="❌ Não tem música pausada agora.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para remover música da fila
@bot.command(name="remove")
async def remover(ctx, indice: int):
    id_servidor = ctx.guild.id
    if id_servidor in filas_musicas and 0 < indice <= len(filas_musicas[id_servidor]):
        musica_removida = filas_musicas[id_servidor].pop(indice - 1)
        embed = discord.Embed(description=f"🗑 Removido: {musica_removida['titulo']}", color=discord.Color.red())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="❌ Índice inválido ou fila vazia.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para mostrar música atual
@bot.command(name="nowplaying")
async def tocando_agora(ctx):
    id_servidor = ctx.guild.id
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        if id_servidor in musica_atual:
            titulo = musica_atual[id_servidor]["titulo"]
            embed = discord.Embed(title="🎵 Tocando Agora", description=f"**{titulo}**", color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description="🎵 Tocando agora: [Música desconhecida]", color=discord.Color.blue())
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="❌ Não tem música tocando agora.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para ajustar volume
@bot.command(name="volume")
async def ajustar_volume(ctx, volume: int):
    if ctx.voice_client:
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100
            embed = discord.Embed(description=f"🔊 Volume ajustado para {volume}%", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description="❌ O volume deve estar entre 0 e 100.", color=discord.Color.red())
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(description="❌ O bot não está em um canal de voz.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para ativar/desativar modo loop
@bot.command(name="loop")
async def loop(ctx):
    id_servidor = ctx.guild.id
    modo_loop[id_servidor] = not modo_loop.get(id_servidor, False)
    status = "ativado" if modo_loop[id_servidor] else "desativado"
    embed = discord.Embed(description=f"🔁 Modo loop {status}.", color=discord.Color.purple())
    await ctx.send(embed=embed)

# Comando para parar e desconectar
@bot.command(name="stop")
async def parar(ctx):
    if ctx.voice_client:
        filas_musicas[ctx.guild.id] = []
        musica_atual.pop(ctx.guild.id, None)
        modo_loop.pop(ctx.guild.id, None)
        await ctx.voice_client.disconnect()
        embed = discord.Embed(description="Saindo do canal de voz. 👋", color=discord.Color.orange())
        await ctx.send(embed=embed)

# Comando para responder perguntas simples
@bot.command(name="perguntar")
async def perguntar(ctx, *, pergunta: str):
    perguntas_respostas = {
        "qual o seu nome?": "Eu sou o Butequinho, o bot mais brabo do servidor! 🎶",
        "como você está?": "Tô de boa, e tu? 😎",
        "qual é a capital do Brasil?": "A capital do Brasil é Brasília, firmeza? 🇧🇷",
        "qual é o seu objetivo?": "Tocar as melhores músicas e ajudar a galera! 🎧",
        "quem te criou?": "Fui criado pelo Natan Fagundes, o cara é brabo! 😎"
    }
    pergunta = pergunta.strip().lower()
    resposta = perguntas_respostas.get(pergunta, "Não entendi, tenta de novo aí!")
    await ctx.send(resposta)

# Comando para exibir ajuda
@bot.command(name="ajuda")
async def ajuda(ctx):
    texto_ajuda = (
        "Comandos disponíveis:\n"
        "!p <nome ou link> - Toca uma música ou adiciona na fila.\n"
        "!skip - Pula a música atual.\n"
        "!queue - Mostra a fila de músicas.\n"
        "!pause - Pausa a música.\n"
        "!resume - Continua a música pausada.\n"
        "!remove <índice> - Remove uma música da fila.\n"
        "!nowplaying - Mostra a música que tá tocando.\n"
        "!volume <0-100> - Ajusta o volume.\n"
        "!loop - Liga/desliga o modo loop.\n"
        "!stop - Para tudo e sai do canal.\n"
        "!oi - Dá um alô maneiro.\n"
        "!hora - Mostra a hora atual.\n"
        "!aplausos - Toca um som de aplausos.\n"
        "!definir <palavra> - Mostra o significado de uma palavra (em inglês).\n"
        "!feedback <msg> - Envia um feedback pro dev.\n"
        "!calcular <expr> - Faz cálculos matemáticos.\n"
        "!meme - Envia um meme aleatório.\n"
        "!limpar <qtd> - Apaga mensagens (precisa de permissão).\n"
    )
    embed = discord.Embed(title="Ajuda do Butequinho", description=texto_ajuda, color=discord.Color.blue())
    await ctx.send(embed=embed)

# Comando para cumprimentar
@bot.command(name="oi")
async def cumprimentar(ctx):
    await ctx.send(f"Fala, {ctx.author.name}! Como posso te ajudar hoje? 👋\nDá um !ajuda se tiver dúvida nos comandos!")

# Comando para mostrar a hora
@bot.command(name="hora")
async def hora(ctx):
    hora_atual = datetime.datetime.now()
    await ctx.send(f"A hora atual é: {hora_atual.strftime('%I:%M %p - %d/%m/%Y, %A')} (horário -03)")

# Comando para tocar aplausos
@bot.command(name="aplausos")
async def aplausos(ctx):
    try:
        if not ctx.author.voice:
            embed = discord.Embed(description="Você precisa estar em um canal de voz!", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        canal = ctx.author.voice.channel
        if not ctx.voice_client:
            await canal.connect()
        elif ctx.voice_client.channel != canal:
            await ctx.voice_client.move_to(canal)

        cliente_voz = ctx.voice_client
        if not cliente_voz.is_connected():
            embed = discord.Embed(description="Não consegui conectar ao canal de voz!", color=discord.Color.red())
            await ctx.send(embed=embed)
            return

        url_aplausos = "https://www.youtube.com/watch?v=7w4sAK_eMSY"
        opcoes_ffmpeg = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -loglevel panic"
        }
        try:
            audio = discord.FFmpegPCMAudio(url_aplausos, executable=caminho_ffmpeg, **opcoes_ffmpeg)
            cliente_voz.play(audio)
            await ctx.send("Aplausos pra você, fera! 👏")
        except Exception as e:
            embed = discord.Embed(description=f"Erro ao tocar aplausos: {str(e)}", color=discord.Color.red())
            await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(title="❌ Erro", description=f"Deu um erro: {str(e)}", color=discord.Color.red())
        await ctx.send(embed=embed)
        print(f"Erro no comando aplausos: {str(e)}")

# Reage a mensagens específicas
@bot.event
async def on_message(mensagem):
    if "bom dia" in mensagem.content.lower():
        await mensagem.add_reaction("☀️")
    elif "desculpa" in mensagem.content.lower():
        await mensagem.add_reaction("🙏")
    elif "oi" in mensagem.content.lower():
        await mensagem.add_reaction("👌🏻")
    await bot.process_commands(mensagem)

# Comando para definir palavras (em inglês)
@bot.command(name="definir")
async def definir_palavra(ctx, *, palavra: str):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{palavra}"
    resposta = requests.get(url).json()
    if "title" in resposta:
        await ctx.send(f"Não achei a definição de '{palavra}'.")
    else:
        definicao = resposta[0]["meanings"][0]["definitions"][0]["definition"]
        await ctx.send(f"A definição de '{palavra}' é: {definicao}")

# Comando para receber feedback
@bot.command(name="feedback")
async def enviar_feedback(ctx, *, mensagem: str):
    await ctx.send(f"Valeu pelo feedback, {ctx.author.name}! 💬")
    print(f"Feedback de {ctx.author.name}: {mensagem}")

# Comando para calcular expressões
@bot.command(name="calcular")
async def calcular(ctx, *, expressao: str):
    try:
        resultado = sp.sympify(expressao)
        await ctx.send(f"O resultado de `{expressao}` é: {resultado}")
    except:
        await ctx.send("Não consegui calcular isso. Dá uma olhada na expressão!")

# Comando para enviar memes
@bot.command(name="meme")
async def meme(ctx):
    resposta = requests.get("https://meme-api.com/gimme")
    dados = resposta.json()
    await ctx.send(dados["url"])

# Comando para limpar mensagens
@bot.command(name="limpar")
@commands.has_permissions(manage_messages=True)
async def limpar_mensagens(ctx, quantidade: int = 100):
    apagadas = await ctx.channel.purge(limit=quantidade)
    confirmacao = await ctx.send(f"{len(apagadas)} mensagens foram apagadas.")
    await asyncio.sleep(5)
    await confirmacao.delete()

# Tratamento de erros
@bot.event
async def on_command_error(ctx, erro):
    if isinstance(erro, commands.MissingPermissions):
        await ctx.send("Você não tem permissão pra usar esse comando!")
    else:
        await ctx.send(f"Deu um erro: {str(erro)}")
        print(f"Erro: {str(erro)}")

# Inicia o bot
bot.run(TOKEN)
