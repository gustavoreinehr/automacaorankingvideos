import os
import json
import subprocess
import time
import re
import sys
import textwrap
import asyncio
import edge_tts
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import yt_dlp

load_dotenv()

BASE_DIR = Path(__file__).parent.absolute()
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_FILE = BASE_DIR / "temas_usados.txt"
FFMPEG_EXE = str(BASE_DIR / "ffmpeg.exe")

# Garantir que as pastas existam
for d in [TEMP_DIR, OUTPUT_DIR]:
    d.mkdir(exist_ok=True)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def clear_temp():
    """Limpa a pasta temporária para evitar conflitos."""
    for f in TEMP_DIR.glob("*"):
        try:
            os.remove(f)
        except:
            pass

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return f.read().splitlines()
    return []

def save_history(theme):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(theme + "\n")

def escape_ffmpeg_text(text):
    """Escapa caracteres especiais para o filtro drawtext do FFmpeg."""
    text = text.replace('\\', '\\\\').replace(':', '\\:')
    text = text.replace("'", "\u2019") 
    return text

def wrap_text_for_ffmpeg(text, max_chars=30):
    """Quebra o texto em linhas para caber na tela."""
    wrapper = textwrap.TextWrapper(width=max_chars)
    lines = wrapper.wrap(text)
    return lines

# --- FUNÇÕES DE INTRODUÇÃO (NOVO) ---

async def generate_tts_audio(text, output_file):
    """Gera áudio narrado usando Edge-TTS (Voz Neural)."""
    # Voz masculina assertiva e rápida (+20%)
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate="+25%")
    await communicate.save(output_file)

def create_intro_video(theme_title, out_path):
    """Cria um vídeo de intro com fundo preto, título e narração."""
    print(f"[*] Criando INTRO para: {theme_title}")
    
    # 1. Gerar o áudio da narração
    audio_path = str(TEMP_DIR / "intro_audio.mp3")
    text_to_say = f"Here is the {theme_title}. Let's go!"
    asyncio.run(generate_tts_audio(text_to_say, audio_path))
    
    # 2. Criar filtros de texto para o título
    title_lines = wrap_text_for_ffmpeg(theme_title.upper(), max_chars=20)
    draw_text_filters = ""
    start_y = 700 # Centralizado verticalmente (aprox)
    font_size = 75
    line_height = 90
    
    for i, line in enumerate(title_lines):
        safe_line = escape_ffmpeg_text(line)
        y_pos = start_y + (i * line_height)
        draw_text_filters += (
            f",drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{safe_line}':"
            f"fontcolor=yellow:fontsize={font_size}:x=(w-text_w)/2:y={y_pos}:"
            f"box=1:boxcolor=black@0.0:borderw=3:bordercolor=black" # Sem box, só borda grossa
        )

    # 3. Gerar vídeo com FFmpeg
    # -f lavfi -i color=c=black:s=1080x1920: Cria fundo preto
    # -shortest: O vídeo dura o tempo do áudio
    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920",
        "-i", audio_path,
        "-filter_complex", 
        f"[0:v]setsar=1{draw_text_filters}[v];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[a]",
        "-map", "[v]", "-map", "[a]",
        "-shortest", # Corta o vídeo quando o áudio acaba
        
        # Encoding padrão (IGUAL AOS OUTROS CLIPES)
        "-c:v", "libx264", "-r", "30", "-g", "60", "-sc_threshold", "0", 
        "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        str(out_path)
    ]
    
    subprocess.run(cmd, check=True)
    return out_path

# --- FIM FUNÇÕES INTRO ---

def generate_ranking_data():
    history = load_history()
    history_str = "\n".join([f"- {h}" for h in history[-20:]])
    
    print("[*] Pedindo para a IA (GROQ) criar um tema e um ranking musical (TOP 10)...")
    prompt = f"""
    Act as an expert viral video producer for TikTok/Shorts and a STRICT Music Historian. 
    You create engaging "Top 10" music rankings. Content must be in ENGLISH.
    
    CRITICAL INSTRUCTION: VERACITY IS PARAMOUNT.
    - Do NOT hallucinate stats.
    - Use ONLY well-established facts (Billboard, RIAA, Spotify, Guinness).
    - PREFER themes based on VISUAL content (Music Videos) rather than abstract stats (Sales).
    
    PREVIOUSLY USED THEMES (DO NOT REPEAT):
    {history_str}
    
    Create a new "Top 10" music theme. 
    Examples: "Top 10 Most Expensive Music Videos", "Top 10 Most Viewed Rock Songs", "Top 10 Iconic 2000s Pop Videos".
    
    Format EXACTLY in JSON. Return ONLY the JSON:
    {{
      "theme_title": "TOP 10 MOST EXPENSIVE MUSIC VIDEOS",
      "ranking": [
         {{
            "rank": 10,
            "artist": "Artist Name",
            "song": "Song Name",
            "stat": "Stat Description"
         }}
      ] 
      // You MUST fill exactly 10 positions (Rank 10 down to 1).
    }}
    """
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        res = chat_completion.choices[0].message.content
        txt = res.replace('```json', '').replace('```', '').strip()
        return json.loads(txt)
    except Exception as e:
        print(f"[!] Erro ao usar a Groq: {e}")
        return {"theme_title": "Error", "ranking": []}

def download_video_trecho(artist, song, out_path):
    search_query = f"{artist} - {song} Official Music Video"
    print(f"[*] Buscando Oficial no YouTube: '{search_query}'")
    
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'match_filter': yt_dlp.utils.match_filter_func("!is_live"), 
        'ignoreerrors': True,
        'default_search': 'ytsearch3', 
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(search_query, download=False)
            
            candidates = []
            if 'entries' in info:
                for entry in info['entries']:
                    if not entry: continue
                    title_lower = entry.get('title', '').lower()
                    
                    score = 0
                    if "official" in title_lower: score += 5
                    if "video" in title_lower: score += 2
                    if "review" in title_lower: score -= 100
                    if "reaction" in title_lower: score -= 100
                    if "cover" in title_lower: score -= 50
                    if "lyrics" in title_lower: score -= 20
                    
                    candidates.append((score, entry))
            
            if not candidates:
                print("[!] Nenhum video valido encontrado.")
                return None
                
            best_video = sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]
            print(f"    -> Selecionado: {best_video['title']} (Score calculado)")
            
            target_url = best_video['webpage_url']
            duration = best_video.get('duration', 180)
            
        except Exception as e:
            print(f"[!] Erro ao buscar: {e}")
            return None

    start_time = max(0, int(duration * 0.35))
    end_time = start_time + 5 
    
    print(f"[*] Baixando trecho (de {start_time}s até {end_time}s)...")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--quiet", "--no-warnings",
        "--download-sections", f"*{start_time}-{end_time}",
        "--force-keyframes-at-cuts",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--ffmpeg-location", str(BASE_DIR),
        "-o", str(out_path),
        target_url
    ]
    
    subprocess.run(cmd)
    
    arquivos_possiveis = list(Path(out_path).parent.glob(out_path.name + "*"))
    if arquivos_possiveis:
        return arquivos_possiveis[0]
    return out_path

def create_text_filter(text, font_size, y_start, color="white", box_color="black@0.6", border_w=3):
    max_chars = 25
    if len(text) > 25:
        max_chars = 30
        font_size = int(font_size * 0.9)
    
    lines = wrap_text_for_ffmpeg(text, max_chars)
    filters = ""
    line_height = font_size + 10
    
    for i, line in enumerate(lines):
        safe_line = escape_ffmpeg_text(line)
        
        if isinstance(y_start, int):
            y_pos = y_start + (i * line_height)
        else:
            offset = i * line_height
            y_pos = f"{y_start}+{offset}"
        
        filters += (
            f",drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{safe_line}':"
            f"fontcolor={color}:fontsize={font_size}:x=(w-text_w)/2:y={y_pos}:"
            f"box=1:boxcolor={box_color}:boxborderw=10:borderw={border_w}"
        )
    return filters

def criar_trecho_video(video_orig, theme_title, rank_info, out_path):
    rank = rank_info['rank']
    artist = rank_info['artist']
    song = rank_info['song']
    stat = rank_info['stat']

    title_filter = create_text_filter(theme_title.upper(), 60, 120, box_color="black@0.7")
    artist_filter = create_text_filter(f"{artist} - {song}", 55, "(h-text_h)/2+200", box_color="black@0.6")
    stat_filter = create_text_filter(f"({stat})", 50, "(h-text_h)/2+350", color="0x00FF00", box_color="black@0.6")
    safe_rank = f"#{rank}"
    
    # ATENÇÃO: [0:a]loudnorm=I=-16:TP=-1.5:LRA=11[a] -> Normaliza o áudio para -16LUFS (Padrão mobile)
    v_filter = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920:(iw-ow)/2:(ih-oh)/2,"
        f"setsar=1," 
        f"colorchannelmixer=rr=0.5:gg=0.5:bb=0.5" 
        f"{title_filter}"
        f",drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{safe_rank}':fontcolor=yellow:fontsize=180:x=(w-text_w)/2:y=(h-text_h)/2-150:borderw=8:bordercolor=black"
        f"{artist_filter}"
        f"{stat_filter}"
    )

    cmd = [
        FFMPEG_EXE, "-y", 
        "-t", "5.0", "-i", str(video_orig),
        "-filter_complex", f"[0:v]{v_filter}[v];[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[a]", 
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-r", "30", "-g", "60", "-sc_threshold", "0", 
        "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        str(out_path)
    ]
    subprocess.run(cmd, check=True)

def main():
    clear_temp()
    print("=" * 50)
    print("🎬 AUTOMACAO TOP 5 (AUDIO PRO & INTRO NARRADA) 🎬")
    print("=" * 50)
    
    dados = generate_ranking_data()
    theme_title = dados.get('theme_title', 'TOP 5 MUSIC RANKING')
    ranking = dados.get('ranking', [])
    
    if not ranking:
        print("[!] Erro: Nenhum ranking gerado.")
        return

    print(f"\n🎼 TEMA: {theme_title}")
    save_history(theme_title)
    
    arquivos_trecho = []
    
    # 1. GERA A INTRO
    try:
        intro_path = TEMP_DIR / "intro_final.mp4"
        create_intro_video(theme_title, intro_path)
        if intro_path.exists():
            arquivos_trecho.append(intro_path)
    except Exception as e:
        print(f"[!] Erro ao criar intro: {e}")

    # 2. GERA OS CLIPES
    ranks = sorted(ranking, key=lambda x: x['rank'], reverse=True)
    
    for r in ranks:
        pos = r['rank']
        print(f"\n[*] Processando #{pos}: {r['artist']} - {r['song']}")
        
        vid_bruto = TEMP_DIR / f"bruto_{pos}.mp4"
        baixado = download_video_trecho(r['artist'], r['song'], vid_bruto)
        
        if not baixado or not Path(baixado).exists():
            print(f"[!] Falha ao baixar #{pos}. Ignorando.")
            continue
            
        vid_pronto = TEMP_DIR / f"pronto_{pos}.mp4"
        try:
            criar_trecho_video(baixado, theme_title, r, vid_pronto)
            if vid_pronto.exists():
                arquivos_trecho.append(vid_pronto)
        except Exception as e:
            print(f"[!] Erro ao processar video #{pos}: {e}")
        
    if not arquivos_trecho:
        print("[!] Nenhum video gerado.")
        return
        
    print("\n[*] 🎞️ Unindo tudo (Intro + Ranking)...")
    concat_txt = TEMP_DIR / "concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in arquivos_trecho:
            safe_path = str(p.name)
            f.write(f"file '{safe_path}'\n")
            
    nome_final = re.sub(r'[^a-zA-Z0-9]', '', theme_title)
    arquivo_final = OUTPUT_DIR / f"Viral_{nome_final}_{int(time.time())}.mp4"
    
    cmd_concat = [
        FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", 
        "-i", str(concat_txt), "-c", "copy", str(arquivo_final)
    ]
    subprocess.run(cmd_concat, check=True, cwd=str(TEMP_DIR))
    
    print(f"\n✅ SUCESSO! Video salvo em:\n{arquivo_final}")
    
if __name__ == "__main__":
    main()
