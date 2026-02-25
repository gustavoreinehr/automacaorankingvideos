# Automação Ranking Music

Este projeto automatiza a criação de vídeos estilo "Top 10" para YouTube Shorts ou TikTok baseados em rankings musicais. Ele utiliza Inteligência Artificial (Groq) para gerar o roteiro e dados do ranking, `yt-dlp` para baixar clipes musicais e `ffmpeg` para edita-los e gerar a narração com `edge-tts`. Conta com uma interface gráfica amigável em Tkinter.

## Funcionalidades
- **Geração por IA**: Gera dinamicamente temas e dados de classificação através da API Groq (llama-3.3-70b-versatile).
- **Download Inteligente**: Pesquisa o clipe oficial no YouTube e faz o download de pequenos trechos para evitar *copyright strikes*.
- **Narração e Textos**: Utiliza `edge-tts` (vozes neurais) para narração da introdução e edita os trechos usando filtros visuais e textos estilizados via FFmpeg.
- **Interface GUI**: Painel de controle simples feito em Python (`tkinter`), com *logs* em tempo real.

## Como usar
1. Instale as dependências executando:
   ```bash
   pip install -r requirements.txt
   ```
2. Crie um arquivo `.env` na raiz do projeto contendo sua chave de API do Groq:
   ```
   GROQ_API_KEY=sua_chave_aqui
   ```
3. Certifique-se de ter os arquivos `ffmpeg.exe` e `ffprobe.exe` na mesma pasta ou configurados no seu PATH. (Não incluídos neste repositório por tamanho).
4. Rode a interface:
   ```bash
   python app_gui.py
   ```
5. Clique em "INICIAR GERAÇÃO" e aguarde! O vídeo será gerado na pasta `output`.

## Tecnologias Usadas
- Python 3.10+
- `groq`
- `yt-dlp`
- `edge-tts`
- `ffmpeg`
- `tkinter`
