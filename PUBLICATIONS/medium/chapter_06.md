---
title: "chapter_06"
platform: "Medium"
tags: ["mathematics", "science", "education"]
date: "2026-08-13T12:22:21.055168"
---




    
    
    Глава 6: Бёрч-Свиннертон-Дайер
    
    
    
    
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
    

    Глава 6: Бёрч-Свиннертон-Дайер
    
    
        Задача
        Гипотеза BSD связывает ранг эллиптической кривой $E$ с поведением $L$-функции $L(E, s)$ в точке $s = 1$.
        
        
            $$\mathrm{ord}_{s=1} L(E, s) = \mathrm{rank}(E(\Q))$$
        
        
        Лемма 6.1: $L(E, s) = \sum_{n=1}^{\infty} a_n n^{-s}$, где $a_p = p + 1 - \#E(\F_p)$.
        Лемма 6.2: Функциональное уравнение: $L(E, s) = \varepsilon \cdot N^{1-s} \cdot (2\pi)^{-s} \cdot \Gamma(s) \cdot L(E, 2-s)$.
    
    
    
        Оптимизация для LLM
        
        1. L-функция
        $L(E, s) = \sum a_n n^{-s}$. Коэффициенты $a_p = p + 1 - \#E(\F_p)$.
        $$L(E, s) = \prod_p (1 - a_p p^{-s} + p^{1-2s})^{-1}$$
        
        2. Функциональное уравнение
        Симметрия относительно $s = 1$.
        $$\Lambda(E, s) = N^{s/2} (2\pi)^{-s} \Gamma(s) L(E, s) = \varepsilon \cdot \Lambda(E, 2-s)$$
        
        3. Ранг и точки
        $\mathrm{rank} = $ число свободных генераторов Mordell-Weil группы.
        $$E(\Q) \cong \Z^r \oplus E(\Q)_{\mathrm{tors}}$$
    
    
    
        Связь с реальным миром
        Криптография: Эллиптические кривые (ECC) — основа современной криптографии. Безопасность зависит от ранга.
        
        Алгебраическая геометрия: Кривые — фундаментальные объекты. BSD связывает арифметику и геометрию.
        
        Числовые методы: Вычисление $L(E, s)$ и ранга — активная область исследований.
        
        См. также: Глава 3: Риман — дзета-функция Римана
    

    
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
                    "\\Q": "\\mathbb{Q}",
                    "\\F": "\\mathbb{F}"
                }
            });
        });
    


