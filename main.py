import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Configuração visual
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Stress Test Pro")
        self.geometry("1100x750")

        self.tempos = []
        self.setup_ui()

    def setup_ui(self):
        # --- Sidebar de Configurações ---
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="⚙️ Parâmetros", font=("Roboto", 20, "bold")).pack(pady=15)

        # Query
        ctk.CTkLabel(self.sidebar, text="Query SQL:").pack(anchor="w", padx=20)
        self.entry_query = ctk.CTkTextbox(self.sidebar, height=80, width=250)
        self.entry_query.insert("0.0", "SELECT 1 + 1")
        self.entry_query.pack(pady=5, padx=20)

        # Total de Conexões
        ctk.CTkLabel(self.sidebar, text="Total de Requisições:").pack(anchor="w", padx=20)
        self.entry_total = ctk.CTkEntry(self.sidebar, width=250)
        self.entry_total.insert(0, "1000")
        self.entry_total.pack(pady=5, padx=20)

        # Simultaneidade (Concorrência)
        ctk.CTkLabel(self.sidebar, text="Simultâneas (Concurrency):").pack(anchor="w", padx=20)
        self.entry_concur = ctk.CTkEntry(self.sidebar, width=250)
        self.entry_concur.insert(0, "50")
        self.entry_concur.pack(pady=5, padx=20)

        # Dados de Conexão
        ctk.CTkLabel(self.sidebar, text="Host MySQL:").pack(anchor="w", padx=20, pady=(10,0))
        self.entry_host = ctk.CTkEntry(self.sidebar, width=250)
        self.entry_host.insert(0, "127.0.0.1")
        self.entry_host.pack(pady=5, padx=20)

        self.entry_user = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Usuário")
        self.entry_user.insert(0, "root")
        self.entry_user.pack(pady=5, padx=20)

        self.entry_pass = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Senha", show="*")
        self.entry_pass.pack(pady=5, padx=20)

        self.entry_db = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Banco de Dados")
        self.entry_db.insert(0, "mysql")
        self.entry_db.pack(pady=5, padx=20)

        # Botão de Ação
        self.btn_start = ctk.CTkButton(self.sidebar, text="🔥 INICIAR STRESS TEST", 
                                      command=self.start_test_thread, 
                                      font=("Roboto", 14, "bold"), height=40)
        self.btn_start.pack(pady=30, padx=20)

        # Resultados Rápidos
        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Status: Pronto", text_color="gray")
        self.lbl_status.pack()
        
        self.lbl_media = ctk.CTkLabel(self.sidebar, text="Média: ---", font=("Roboto", 18, "bold"))
        self.lbl_media.pack(pady=10)

        # --- Área do Gráfico ---
        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.fig.patch.set_facecolor('#1e1e1e')
        self.ax.tick_params(colors='white')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_content)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def update_graph(self):
        self.ax.clear()
        self.ax.set_title("Latência em Milissegundos (ms)", color="white", pad=20)
        self.ax.plot(self.tempos, color="#3b8ed0", linewidth=1.5)
        self.ax.set_ylabel("Tempo (ms)", color="white")
        self.ax.grid(True, linestyle='--', alpha=0.2)
        self.canvas.draw()

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        self.tempos = []
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306}

        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))

            async def task():
                async with sem:
                    start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query)
                                await cur.fetchone()
                        end = time.perf_counter()
                        self.tempos.append((end - start) * 1000)
                    except Exception:
                        self.tempos.append(0) # Falha

            tasks = [task() for _ in range(int(total))]
            await asyncio.gather(*tasks)
            
            pool.close()
            await pool.wait_closed()
            
            if self.tempos:
                avg = sum(self.tempos) / len(self.tempos)
                self.lbl_media.configure(text=f"Média: {avg:.2f}ms")
                self.lbl_status.configure(text="✅ Finalizado com sucesso!", text_color="green")
            self.update_graph()

        except Exception as e:
            self.lbl_status.configure(text=f"❌ Erro de Conexão", text_color="red")
            print(f"Erro: {e}")
        
        self.btn_start.configure(state="normal", text="🔥 INICIAR STRESS TEST")

    def start_test_thread(self):
        # Coleta dados da UI
        query = self.entry_query.get("0.0", "end").strip()
        total = self.entry_total.get()
        concur = self.entry_concur.get()
        host = self.entry_host.get()
        user = self.entry_user.get()
        pw = self.entry_pass.get()
        db = self.entry_db.get()

        self.btn_start.configure(state="disabled", text="⏳ PROCESSANDO...")
        self.lbl_status.configure(text="🚀 Executando queries...", text_color="cyan")
        
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run_stress_test(query, total, concur, host, user, pw, db))

        threading.Thread(target=run_loop, daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
