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
from card_generator import generate_frames_for_clip
import imageio_ffmpeg

load_dotenv()

BASE_DIR = Path(__file__).parent.absolute()
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_FILE = BASE_DIR / "temas_usados.txt"
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

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

def create_intro_video(theme_title, hook_text, out_path, bg_video=None):
    """Cria um vídeo de intro com título, gancho narrado e fundo dinâmico."""
    print(f"[*] Criando INTRO com HOOK: {hook_text}")
    
    # 1. Gerar o áudio da narração (Theme + Hook)
    audio_path = str(TEMP_DIR / "intro_audio.mp3")
    text_to_say = f"{theme_title}. {hook_text}"
    asyncio.run(generate_tts_audio(text_to_say, audio_path))
    
    # 2. Filtros de texto
    title_lines = wrap_text_for_ffmpeg(theme_title.upper(), max_chars=15)
    hook_lines = wrap_text_for_ffmpeg(hook_text.upper(), max_chars=20)
    
    draw_filters = ""
    # Título (Cima)
    for i, line in enumerate(title_lines):
        safe_line = escape_ffmpeg_text(line)
        draw_filters += (f",drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{safe_line}':"
                         f"fontcolor=yellow:fontsize=80:x=(w-text_w)/2:y=600+({i}*100):borderw=4")
    
    # Hook (Meio/Baixo)
    for i, line in enumerate(hook_lines):
        safe_line = escape_ffmpeg_text(line)
        draw_filters += (f",drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{safe_line}':"
                         f"fontcolor=white:fontsize=65:x=(w-text_w)/2:y=1100+({i}*80):borderw=4")

    # 3. Configurar entrada de vídeo
    if bg_video and Path(bg_video).exists():
        v_input = ["-i", str(bg_video)]
        v_filter = f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:(iw-ow)/2:(ih-oh)/2,boxblur=25:25,colorchannelmixer=rr=0.5:gg=0.5:bb=0.5{draw_filters}[v]"
    else:
        v_input = ["-f", "lavfi", "-i", "color=c=black:s=1080x1920"]
        v_filter = f"[0:v]setsar=1{draw_filters}[v]"

    cmd = [
        FFMPEG_EXE, "-y",
        *v_input,
        "-i", audio_path,
        "-filter_complex", f"{v_filter};[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[a]",
        "-map", "[v]", "-map", "[a]",
        "-shortest",
        "-c:v", "libx264", "-r", "30", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k", str(out_path)
    ]
    
    subprocess.run(cmd, check=True)
    return out_path

# --- FIM FUNÇÕES INTRO ---

def generate_ranking_data():
    history = load_history()
    history_str = "\n".join([f"- {h}" for h in history[-20:]])
    
    print("[*] Pedindo para a IA criar um tema, ranking e um HOOK viral...")
    
    # Lista de modelos para fallback caso um falhe ou esteja congestionado
    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
        "llama3-70b-8192"
    ]
    
    prompt = f"""
    Act as a STRICT Music Historian and Viral Producer. 
    Your goal is to create a "Top 10" or "Top 5" ranking based on 100% REAL and VERIFIED data.
    
    CRITICAL CONSTRAINTS:
    - DATA VERACITY: Do NOT hallucinate. Use data from Billboard, RIAA, Guinness World Records, or official YouTube/Spotify counts.
    - THEME: Must be music-related and visual (must have a Music Video).
    - ITEMS: Each item MUST include "artist", "song", and the exact "stat" (e.g., "3.2 Billion Views", "14 Weeks at #1").
    - STARTING HOOK: Create a "hook_text" that references the data (e.g., "These numbers are legendary!").
    
    PREVIOUSLY USED (DO NOT REPEAT):
    {history_str}
    
    Return ONLY JSON:
    {{
      "theme_title": "TOP 10 MOST CERTIFIED SONGS (RIAA)",
      "hook_text": "The winner has 15 Diamond certifications!",
      "ranking": [
         {{
            "rank": 10,
            "artist": "Artist Name",
            "song": "Song Name",
            "stat": "11x Platinum"
         }}
      ]
    }}
    """
    
    for model_name in models_to_try:
        try:
            print(f"[*] Tentando modelo: {model_name}...")
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
            )
            res = chat_completion.choices[0].message.content
            txt = res.replace('```json', '').replace('```', '').strip()
            return json.loads(txt)
        except Exception as e:
            print(f"[!] Erro com o modelo {model_name}: {e}")
            continue # Tenta o próximo modelo
            
    print("[!] Todos os modelos de IA falharam.")
    return {"theme_title": "Error", "ranking": [], "hook_text": "Let's find out!"}

def download_video_trecho(artist, song, out_path, duration_sec=7):
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
                    channel_lower = entry.get('uploader', '').lower()
                    
                    score = 0
                    # Bonus por canal oficial e VEVO
                    if "vevo" in channel_lower or channel_lower.endswith("- topic"): score += 50
                    if artist.lower() in channel_lower: score += 30
                    
                    # Bonus por título exato
                    if "official" in title_lower: score += 20
                    if song.lower() in title_lower: score += 20
                    if "video" in title_lower or "music" in title_lower: score += 10
                    
                    # Penalidades severas para evitar lixo
                    if any(x in title_lower for x in ["review", "reaction", "cover", "lyrics", "live", "fan-made", "parody", "karaoke", "remix"]):
                        score -= 200
                    if any(x in channel_lower for x in ["reaction", "lyrics"]):
                        score -= 150
                    
                    candidates.append((score, entry))
            
            if not candidates:
                print("[!] Nenhum video valido encontrado.")
                return None, None
                
            # Seleciona o que tiver o score mais alto
            best_video = sorted(candidates, key=lambda x: x[0], reverse=True)[0][1]
            print(f"    -> Selecionado: {best_video['title']} [Score: {sorted(candidates, key=lambda x: x[0], reverse=True)[0][0]}]")
            
            target_url = best_video['webpage_url']
            duration = best_video.get('duration', 180)
            
        except Exception as e:
            print(f"[!] Erro ao buscar: {e}")
            return None, None

    start_time = max(0, int(duration * 0.35))
    end_time = start_time + duration_sec
    
    print(f"[*] Baixando trecho (de {start_time}s até {end_time}s)...")
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--quiet", "--no-warnings",
        "--download-sections", f"*{start_time}-{end_time}",
        "--force-keyframes-at-cuts",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--ffmpeg-location", FFMPEG_EXE,
        "-o", str(out_path),
        target_url
    ]
    
    subprocess.run(cmd)
    
    arquivos_possiveis = list(Path(out_path).parent.glob(out_path.name + "*"))
    if arquivos_possiveis:
        baixado = arquivos_possiveis[0]
        # Extrair thumbnail (primeiro frame)
        thumb_path = out_path.with_suffix('.jpg')
        cmd_thumb = [
            FFMPEG_EXE, "-y", "-i", str(baixado), "-vframes", "1", "-q:v", "2", str(thumb_path)
        ]
        subprocess.run(cmd_thumb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return baixado, thumb_path
    return out_path, None

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

def criar_trecho_video(video_orig, theme_title, rank_info, out_path, thumb_path, start_offset=0):
    print(f"[*] Extraindo frames do vídeo para animação circular (start: {start_offset}s)...")
    video_frames_dir = TEMP_DIR / f"video_frames_{rank_info['rank']}"
    video_frames_dir.mkdir(exist_ok=True)
    
    cmd_extract = [
        FFMPEG_EXE, "-y", "-ss", str(start_offset), "-i", str(video_orig),
        "-t", "7.0",
        "-vf", "fps=30,crop='min(iw,ih)':'min(iw,ih)',scale=300:300",
        "-q:v", "2", str(video_frames_dir / "thumb_%04d.jpg")
    ]
    subprocess.run(cmd_extract, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[*] Gerando UI Cards animados para #{rank_info['rank']}...")
    frames_dir = generate_frames_for_clip(TEMP_DIR, rank_info, theme_title, video_frames_dir=video_frames_dir, duration=7.0, fps=30)
    
    # Sequence de imagens
    frames_input = str(Path(frames_dir) / "frame_%04d.png").replace('\\', '/')
    
    # Fundo do vídeo (blur e escurecimento + Fade)
    v_filter = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920:(iw-ow)/2:(ih-oh)/2,"
        f"setsar=1," 
        f"boxblur=20:20,"
        f"colorchannelmixer=rr=0.4:gg=0.4:bb=0.4,"
        f"fade=t=in:st=0:d=0.5,fade=t=out:st=6.5:d=0.5[bg];" # Fades de 0.5s
        f"[1:v]scale=1080:1920,fade=t=in:st=0:d=0.5,fade=t=out:st=6.5:d=0.5[overlay];"
        f"[bg][overlay]overlay=0:0[v]"
    )

    cmd = [
        FFMPEG_EXE, "-y", 
        "-ss", str(start_offset), "-t", "7.0", "-i", str(video_orig),
        "-framerate", "30", "-i", frames_input, # Imagens do card
        "-filter_complex", f"{v_filter};[0:a]afade=t=in:st=0:d=0.5,afade=t=out:st=6.5:d=0.5,loudnorm=I=-16:TP=-1.5:LRA=11[a]", 
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
    
    arquivos_ranking = []
    video_para_intro = None
    arquivos_finais = []
    
    # 1. GERA OS CLIPES DO RANKING PRIMEIRO
    # Garantir que o rank seja inteiro para ordenação correta
    for item in ranking:
        try:
            item['rank'] = int(item['rank'])
        except:
            pass
            
    ranks = sorted(ranking, key=lambda x: x['rank'], reverse=True)
    
    primeiro_processado = True
    intro_duration = 4.0
    
    for r in ranks:
        pos = r['rank']
        print(f"\n[*] Processando #{pos}: {r['artist']} - {r['song']}")
        
        vid_bruto = TEMP_DIR / f"bruto_{pos}.mp4"
        
        # Se for o primeiro (ex: #10), baixar tempo extra para a intro
        duracao_download = 7 + intro_duration if primeiro_processado else 7
        baixado, thumb_path = download_video_trecho(r['artist'], r['song'], vid_bruto, duration_sec=duracao_download)
        
        if not baixado or not Path(baixado).exists():
            print(f"[!] Falha ao baixar #{pos}. Ignorando.")
            continue
            
        # O primeiro vídeo baixado será usado como fundo da intro (take contínuo)
        if primeiro_processado:
            video_para_intro = baixado
            # Criar a intro usando os primeiros segundos do primeiro clipe
            try:
                hook_text = dados.get('hook_text', "Wait until you see #1!")
                intro_path = TEMP_DIR / "intro_final.mp4"
                # A intro só usa o início do vídeo
                create_intro_video(theme_title, hook_text, intro_path, bg_video=video_para_intro)
                if intro_path.exists():
                    arquivos_finais.append(intro_path)
            except Exception as e:
                print(f"[!] Erro ao criar intro dinâmica: {e}")

        vid_pronto = TEMP_DIR / f"pronto_{pos}.mp4"
        try:
            # Se for o primeiro, o clipe do ranking começa após a intro
            offset = intro_duration if primeiro_processado else 0
            criar_trecho_video(baixado, theme_title, r, vid_pronto, thumb_path, start_offset=offset)
            if vid_pronto.exists():
                arquivos_ranking.append(vid_pronto)
        except Exception as e:
            print(f"[!] Erro ao processar video #{pos}: {e}")
            
        primeiro_processado = False

    # Adiciona os clipes do ranking após a intro já adicionada
    arquivos_finais.extend(arquivos_ranking)
        
    if not arquivos_finais:
        print("[!] Nenhum video gerado.")
        return
        
    print("\n[*] 🎞️ Unindo tudo (Intro Dinâmica + Ranking)...")
    concat_txt = TEMP_DIR / "concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in arquivos_finais:
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
