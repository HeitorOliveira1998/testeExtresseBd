import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Stress Test Pro")
        self.geometry("1100x750")

        self.tempos = []
        self.stop_event = threading.Event() # Evento para controlar a parada
        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="⚙️ Parâmetros", font=("Roboto", 20, "bold")).pack(pady=15)

        # Campos de entrada
        self.create_label_entry("Query SQL:", "SELECT 1 + 1", is_textbox=True)
        self.create_label_entry("Total de Requisições:", "1000", attr_name="entry_total")
        self.create_label_entry("Simultâneas (Concurrency):", "50", attr_name="entry_concur")
        self.create_label_entry("Host MySQL:", "127.0.0.1", attr_name="entry_host")
        self.create_label_entry("Usuário:", "root", attr_name="entry_user")
        
        self.entry_pass = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Senha", show="*")
        self.entry_pass.pack(pady=5, padx=20)

        self.entry_db = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Banco de Dados")
        self.entry_db.insert(0, "mysql")
        self.entry_db.pack(pady=5, padx=20)

        # BOTÕES
        self.btn_start = ctk.CTkButton(self.sidebar, text="🔥 INICIAR TESTE", 
                                      command=self.start_test_thread, 
                                      font=("Roboto", 14, "bold"), height=40, fg_color="green")
        self.btn_start.pack(pady=(20, 10), padx=20)

        self.btn_stop = ctk.CTkButton(self.sidebar, text="🛑 PARAR TESTE", 
                                     command=self.stop_test, 
                                     font=("Roboto", 14, "bold"), height=40, fg_color="red", state="disabled")
        self.btn_stop.pack(pady=5, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Status: Pronto", text_color="gray")
        self.lbl_status.pack()
        
        self.lbl_media = ctk.CTkLabel(self.sidebar, text="Média: ---", font=("Roboto", 18, "bold"))
        self.lbl_media.pack(pady=10)

        # Gráfico
        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.fig.patch.set_facecolor('#1e1e1e')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_content)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def create_label_entry(self, text, default, is_textbox=False, attr_name=None):
        ctk.CTkLabel(self.sidebar, text=text).pack(anchor="w", padx=20)
        if is_textbox:
            self.entry_query = ctk.CTkTextbox(self.sidebar, height=70, width=250)
            self.entry_query.insert("0.0", default)
            self.entry_query.pack(pady=5, padx=20)
        else:
            entry = ctk.CTkEntry(self.sidebar, width=250)
            entry.insert(0, default)
            entry.pack(pady=5, padx=20)
            setattr(self, attr_name, entry)

    def stop_test(self):
        """Sinaliza para o loop parar."""
        self.stop_event.set()
        self.lbl_status.configure(text="🛑 Parando...", text_color="orange")

    def update_graph(self):
        self.ax.clear()
        self.ax.set_title("Latência (ms)", color="white")
        self.ax.plot(self.tempos, color="#3b8ed0")
        self.ax.tick_params(colors='white')
        self.canvas.draw()

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        self.tempos = []
        self.stop_event.clear()
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306}

        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))

            async def task():
                if self.stop_event.is_set(): return # Checa se deve parar
                
                async with sem:
                    if self.stop_event.is_set(): return
                    start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query)
                                await cur.fetchone()
                        end = time.perf_counter()
                        self.tempos.append((end - start) * 1000)
                    except:
                        self.tempos.append(0)

            # Criar lista de tarefas
            tasks = [task() for _ in range(int(total))]
            
            # Executar tarefas uma a uma respeitando o semáforo e o stop_event
            for f in asyncio.as_completed(tasks):
                if self.stop_event.is_set():
                    break
                await f
            
            pool.close()
            await pool.wait_closed()
            
            status_text = "✅ Finalizado!" if not self.stop_event.is_set() else "🛑 Interrompido pelo usuário"
            self.lbl_status.configure(text=status_text, text_color="orange" if self.stop_event.is_set() else "green")
            
            if self.tempos:
                avg = sum(self.tempos) / len(self.tempos)
                self.lbl_media.configure(text=f"Média: {avg:.2f}ms")
            self.update_graph()

        except Exception as e:
            self.lbl_status.configure(text="❌ Erro de Conexão", text_color="red")
        
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def start_test_thread(self):
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        
        args = (
            self.entry_query.get("0.0", "end").strip(),
            self.entry_total.get(),
            self.entry_concur.get(),
            self.entry_host.get(),
            self.entry_user.get(),
            self.entry_pass.get(),
            self.entry_db.get()
        )

        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run_stress_test(*args))

        threading.Thread(target=run_loop, daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
