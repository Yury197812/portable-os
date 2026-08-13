---
title: "chapter_04"
platform: "Medium"
tags: ["mathematics", "science", "education"]
date: "2026-08-13T12:22:21.053168"
---




    
    
    Глава 4: Янг-Миллс
    
    
    
    
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Georgia', serif;
            background: #1a1a2e;
            color: #e0e0e0;
            line-height: 1.8;
            padding: 40px;
            max-width: 900px;
            margin: 0 auto;
        }
        nav {
            background: rgba(0,210,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        nav a {
            color: #00d2ff;
            text-decoration: none;
            padding: 5px 10px;
            border-radius: 5px;
            transition: background 0.3s;
        }
        nav a:hover { background: rgba(0,210,255,0.2); }
        nav a.active { background: #00d2ff; color: #1a1a2e; }
        h1 { color: #00d2ff; font-size: 2.5em; margin-bottom: 30px; }
        h2 { color: #3a7bd5; font-size: 1.8em; margin: 30px 0 15px; }
        h3 { color: #00ff88; font-size: 1.3em; margin: 20px 0 10px; }
        .section {
            background: rgba(0,210,255,0.05);
            border-left: 4px solid #00d2ff;
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 10px 10px 0;
        }
        .optimization {
            background: rgba(0,255,136,0.05);
            border-left: 4px solid #00ff88;
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 10px 10px 0;
        }
        code {
            background: rgba(0,0,0,0.3);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            color: #00ff88;
        }
        .formula {
            text-align: center;
            font-size: 1.3em;
            padding: 20px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            margin: 20px 0;
        }
        .cross-ref {
            color: #3a7bd5;
            text-decoration: underline;
            cursor: pointer;
        }
    


    
        0. Введение
        1. P vs NP
        2. Ходжа
        3. Риман
        4. Янг-Миллс
        5. Навье-Стокс
        6. BSD
        7. Связи
    

    Глава 4: Янг-Миллс
    
    
        Задача
        Существование квантовой теории поля для Янг-Миллса и массовый gap — existence калибровочного поля с положительной массой.
        
        
            $$F_{\mu\nu} = \partial_\mu A_\nu - \partial_\nu A_\mu + g[A_\mu, A_\nu]$$
        
        
        Лемма 4.1: Бета-функция $\beta(g) 
        Лемма 4.2: Конфайнмент: потенциал между кварками растёт линейно $V(r) \sim \sigma r$.
    
    
    
        Оптимизация для LLM
        
        1. Бета-функция
        $\beta(g) = -\frac{g^3}{16\pi^2} \left(\frac{11}{3}C_2(G) - \frac{2}{3}N_f\right)$. Положительный $b_0 = 7$ → конфайнмент.
        $$\beta(g) = -b_0 \frac{g^3}{16\pi^2} + O(g^5), \quad b_0 = \frac{11}{3}C_2(G) - \frac{2}{3}N_f$$
        
        2. Групповая структура
        $SU(N)$ — симметрия. Casimir $C_2(SU(3)) = 3$.
        $$C_2(SU(N)) = N, \quad \mathrm{Tr}(T^a T^b) = \tfrac{1}{2}\delta^{ab}$$
        
        3. Конфайнмент
        Сильная связь → глуоны не свободны. Mass gap $> 0$.
        $$\langle 0 | A_\mu^a(x) A_\nu^b(0) | 0 \rangle \sim e^{-M|x|} \delta^{ab}$$
    
    
    
        Связь с реальным миром
        Квантовая хромодинамика: Янг-Миллс — основа Стандартной модели. Конфайнмент объясняет адронную структуру.
        
        Частицы: Глуоны, $W/Z$ бозоны — калибровочные бозоны. Mass gap определяет их массы.
        
        Высокие энергии: LHC проверяет предсказания Янг-Миллса на TeV масштабе.
        
        См. также: Глава 1: P vs NP — вычислительная сложность
    

    
        document.addEventListener("DOMContentLoaded", function() {
            renderMathInElement(document.body, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false}
                ],
                macros: {
                    "\\BigO": "\\mathcal{O}",
                    "\\R": "\\mathbb{R}",
                    "\\C": "\\mathbb{C}",
                    "\\Z": "\\mathbb{Z}",
                    "\\N": "\\mathbb{N}",
                    "\\Q": "\\mathbb{Q}"
                }
            });
        });
    


