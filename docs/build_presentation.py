"""Build index.html from shell + slides (projector-friendly, 13 slides)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
SHELL = Path(__file__).resolve().parent / "presentation-shell.html"
SLIDES = Path(__file__).resolve().parent / "_parking_slides.html"
TOTAL = 13

PARKING_CSS = Path(__file__).resolve().parent.joinpath("_parking_proj.css").read_text(encoding="utf-8") if Path(__file__).resolve().parent.joinpath("_parking_proj.css").exists() else """
      .proj-slide { max-width: 1100px; margin: 0 auto; }
      .proj-heading {
        display: block !important;
        font-size: clamp(42px, 5.5vw, 64px) !important;
        font-weight: 800 !important;
        color: var(--fg) !important;
        margin-bottom: 36px !important;
        letter-spacing: -1px;
        line-height: 1.15;
      }
      .proj-heading .blue { color: var(--accent); }
      .proj-heading .green { color: var(--accent2); }
      .proj-sub { font-size: clamp(22px, 2.8vw, 30px); color: var(--muted); margin: -20px 0 28px; text-align: center; }
      .proj-cover { display: flex; align-items: center; justify-content: center; min-height: 85vh; padding: 0 60px; }
      .proj-welcome { text-align: center; width: 100%; }
      .proj-logo { height: clamp(100px, 14vw, 160px); border-radius: 50%; margin-bottom: 32px; }
      .proj-hero {
        display: block !important;
        font-size: clamp(48px, 7vw, 88px) !important;
        font-weight: 900 !important;
        color: var(--fg) !important;
        line-height: 1.1; margin-bottom: 20px; letter-spacing: -2px;
      }
      .proj-tagline { font-size: clamp(26px, 3.2vw, 40px); color: var(--muted); margin-bottom: 16px; }
      .proj-meta { font-size: clamp(20px, 2.4vw, 28px); color: var(--accent); font-weight: 600; }
      .proj-agenda { list-style: none; display: flex; flex-direction: column; gap: 14px; }
      .proj-agenda li {
        font-size: clamp(24px, 3vw, 38px); font-weight: 600; padding: 14px 22px;
        border-left: 6px solid var(--accent); background: rgba(255,255,255,0.04); border-radius: 0 12px 12px 0;
      }
      .proj-bullets { list-style: none; display: flex; flex-direction: column; gap: 20px; }
      .proj-bullets li { font-size: clamp(24px, 3vw, 36px); line-height: 1.45; }
      .proj-bullets strong { color: var(--accent); }
      .proj-structure { list-style: none; }
      .proj-structure li { font-size: clamp(24px, 3vw, 36px); margin-bottom: 18px; }
      .proj-steps { list-style: none; counter-reset: step; display: flex; flex-direction: column; gap: 18px; }
      .proj-steps li {
        font-size: clamp(24px, 3vw, 36px); padding-left: 56px; position: relative; line-height: 1.45;
      }
      .proj-steps li::before {
        counter-increment: step; content: counter(step);
        position: absolute; left: 0; width: 40px; height: 40px; background: var(--accent);
        color: white; border-radius: 50%; font-weight: 800; font-size: 20px;
        display: flex; align-items: center; justify-content: center; top: 2px;
      }
      .proj-steps code { font-size: clamp(20px, 2.4vw, 28px); color: var(--accent2); background: rgba(0,0,0,0.35); padding: 4px 12px; border-radius: 8px; }
      .proj-flow { display: flex; flex-direction: column; gap: 6px; }
      .proj-flow-step {
        font-size: clamp(22px, 2.8vw, 32px); font-weight: 600; padding: 14px 20px;
        background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid var(--border);
        display: flex; align-items: center; gap: 14px;
      }
      .proj-flow-step span {
        width: 40px; height: 40px; background: var(--accent); color: white; border-radius: 50%;
        display: flex; align-items: center; justify-content: center; font-weight: 800; flex-shrink: 0;
      }
      .proj-flow-arrow { text-align: center; font-size: 28px; color: var(--accent); }
      .proj-team .member-circle.proj-avatar {
        width: clamp(100px, 11vw, 140px); height: clamp(100px, 11vw, 140px);
        display: flex; align-items: center; justify-content: center;
        background: var(--accent-dim); border: 4px solid var(--accent); border-radius: 50%;
      }
      .proj-team .member-circle span { font-size: clamp(32px, 4vw, 44px); font-weight: 900; color: var(--accent); }
      .proj-name { font-size: clamp(18px, 2.2vw, 26px) !important; }
      .proj-role { font-size: clamp(13px, 1.5vw, 17px) !important; }
      .proj-thank { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 80vh; }
      .proj-logo-sm { height: clamp(80px, 10vw, 120px); border-radius: 50%; margin-bottom: 40px; }
      .proj-thank-title {
        display: block !important;
        font-size: clamp(72px, 12vw, 140px) !important;
        font-weight: 900 !important;
        background: linear-gradient(135deg, var(--accent), var(--accent2));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        letter-spacing: -3px; line-height: 1;
      }
      .proj-demo .proj-steps li { font-size: clamp(26px, 3.2vw, 38px); }
"""

HEADER_BODY = f"""  <body>
    <canvas id="bgCanvas"></canvas>
    <div class="glow-blob g1"></div>
    <div class="glow-blob g2"></div>
    <div class="progress-bar" id="progressBar"></div>
    <header class="persistent-header">
      <div class="header-left">
        <img src="frontend/app/assets/image/logo.png" alt="IoT Parking" class="header-logo" />
        <span id="headerSlideTitle">IoT Smart Parking</span>
      </div>
      <div class="header-right"><i data-lucide="parking-square" style="width:36px;height:36px;color:var(--accent)"></i></div>
    </header>
    <div class="nav-controls">
      <button id="btnPrevHeader" class="nav-btn" title="Previous"><i data-lucide="chevron-left"></i></button>
      <div class="header-counter">
        <span class="current" id="counterCurrentHeader">01</span><span style="opacity:0.5"> / </span><span class="total">{TOTAL:02d}</span>
      </div>
      <button id="btnNextHeader" class="nav-btn" title="Next"><i data-lucide="chevron-right"></i></button>
    </div>
    <div class="dot-nav" id="dotNav"></div>
"""


def main() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    slides = SLIDES.read_text(encoding="utf-8")
    out = shell.replace("<!-- PARKING_CSS -->", PARKING_CSS.strip())
    out = out.replace("<!-- HEADER_BODY -->", HEADER_BODY)
    out = out.replace("<!-- SLIDES -->", slides)
    out = out.replace("<title>IoT Smart Parking — Presentation</title>", f"<title>IoT Smart Parking — Presentation ({TOTAL} slides)</title>")
    INDEX.write_text(out, encoding="utf-8")
    print(f"Wrote {INDEX} ({TOTAL} slides)")


if __name__ == "__main__":
    main()
