import asyncio
import websockets
import shlex

class Servidor:
    def __init__(self):
        self.list_conectados = []
        #restringe certos nomes, impedindo que sejam utilizados para cadastrar nicknames de clientes
        self.restricted_names = ["SISTEMA","SYSTEM","SERVIDOR","SERVER","ADMINISTRADOR","ADMIN"]
    
    @property
    def n_usuarios(self):
        return len(self.list_conectados)

    async def conecta(self, websocket, path):
        cliente = Cliente(self, websocket, path)
        if cliente not in self.list_conectados: 
            self.list_conectados.append(cliente)
        
        await cliente.gerencia()     

    async def desconecta(self, cliente):
        #apenas desconecta cliente caso ele esteja conectado
        if cliente in self.list_conectados:
            self.list_conectados.remove(cliente)
        await self.sistema_broadcast("{0} saiu do chat!".format(cliente.nome))
        print("{1} saiu. Total: {0}".format(self.n_usuarios, cliente.nome))            

    async def envia_broadcast(self, origem, mensagem):
        print("Broadcast...")
        for cliente in self.list_conectados:
            #enviar para todos menos usuário que gerou a mensagem            
            if origem != cliente and cliente.conectado:
                #log no terminal do servidor
                print("Enviando de <{0}> para <{1}>: {2}".format(origem.nome, cliente.nome, mensagem))
                #display da mensagem para todos os outros clientes
                await cliente.envia("{0} >> {1}".format(origem.nome, mensagem))

    async def sistema_broadcast(self, mensagem):
        print("Sistema Broadcast...")
        #log no terminal do servidor
        print("Mensagem do sistema para todos os usuários: {0}".format(mensagem)) 
        
        for cliente in self.list_conectados:
            if cliente.conectado:     
                #display da mensagem para todos os outros clientes
                await cliente.envia("SISTEMA >> {0}".format(mensagem))

    async def envia_privado(self, origem, mensagem, destinatario):        
        for cliente in self.list_conectados:            
            if cliente.nome == destinatario and origem != cliente and cliente.conectado:
                #log no terminal do servidor
                print("Enviando de <{0}> para <{1}>: {2}".format(origem.nome, cliente.nome, mensagem))
                #display da mensagem para o destinatário
                await cliente.envia("PRIVADO - {0} >> {1}".format(origem.nome, mensagem))
                return True
        return False

    def verifica_nome(self, nome):
        #varrer lista de clientes para verificar que não ocorrerá repetição
        for cliente in self.list_conectados:
            if cliente.nome and cliente.nome == nome:
                print("Nome inválido")
                return False
        
        if nome in self.restricted_names:
            print("Nome inválido")
            return False
        else:
            return True

    async def listar_usuarios(self, cliente):

        print("{0} requisitou lista de usuários conectados".format(cliente.nome))
        await cliente.envia("SISTEMA >> Enviando lista de usuários")

        lista_ordenada=sorted(self.list_conectados)

        for cliente in lista_ordenada:
            await cliente.envia(str(cliente.nome))
        await cliente.envia("SISTEMA >> Fim da lista de usuários")

    async def buscar_usuario(self,cliente,destinatario):

        print("{0} buscou pelo nickname '{1}'".format(cliente.nome,destinatario))
        if destinatario in self.list_conectados:
            await cliente.envia("SISTEMA >> {0} está conectado!".format(destinatario))
        else:
            await cliente.envia("SISTEMA >> {0} NÂO está conectado! :(".format(destinatario))

class Cliente:    
    def __init__(self, servidor, websocket, path):
        self.cliente = websocket
        self.servidor = servidor
        self.nome = None        
    
    @property
    def conectado(self):
        return self.cliente.open

    async def gerencia(self):
        try:
            await self.envia("Bem vindo ao servidor de chat Papear(TM). Configure seu nickname usando o formato: /nome nome_escolhido")
            while True:
                mensagem = await self.recebe()
                if mensagem:
                    print("{0} < {1}".format(self.nome, mensagem))
                    await self.processa_comandos(mensagem)                                            
                else:
                    break
        except Exception:
            print("Erro")
            raise        
        finally:
            self.servidor.desconecta(self)

    async def envia(self, mensagem):
        await self.cliente.send(mensagem)

    async def recebe(self):
        mensagem = await self.cliente.recv()
        return mensagem

    async def processa_comandos(self, mensagem):        
        if mensagem.strip().startswith("/"):
            comandos=shlex.split(mensagem.strip()[1:])
            if len(comandos)==0:
                await self.envia("Comando inválido")
                return
            print(comandos)
            keyword = comandos[0].lower()            
            
            if keyword == "nome":
                await self.altera_nome(comandos)
            elif keyword == "privado":
                await self.msg_privada(comandos)
            elif keyword == "listar":
                await self.listar_usuarios()
            elif keyword == "buscar":
                await self.buscar_usuario(comandos)
            else:
                await self.envia("Comando não pôde ser reconhecido")
        else:
            #enviar para todos no chat verificando se já tem nickname registrado
            if self.nome:
                await self.servidor.envia_broadcast(self, mensagem)
            else:
                await self.envia("É necessário se identificar antes de enviar mensagens. Configure seu nickname usando o formato: /nome nome_escolhido")

    async def altera_nome(self, comandos):                
        if len(comandos)>1:
            if self.servidor.verifica_nome(comandos[1]):
                #broadcast para todos os usuários avisando que o nickname anterior não está mais em utilização, caso ele tenha sido alterado
                if self.nome != None:
                    await self.servidor.sistema_broadcast("{0} saiu do chat!".format(self.nome))
                else:
                    self.nome = comandos[1]
                    await self.envia("Nome alterado com sucesso para {0}".format(self.nome))
                    await self.servidor.sistema_broadcast("{0} entrou no chat!".format(self.nome))
            else:
                await self.envia("Nome em uso ou inválido. Tente outro nome.")
        else:
            await self.envia("Comando inválido.Configure seu nickname usando o formato: /nome nome_escolhido")
    
    async def msg_privada(self, comandos):
        if len(comandos)<3:
            await self.envia("Comando incorreto. Usar o formato: /apenas destinatário mensagem")
            return
        destinatario = comandos[1]
        mensagem = " ".join(comandos[2:])
        enviado = await self.servidor.envia_privado(self, mensagem, destinatario)
        if not enviado:
            await self.envia("Destinatário {0} não encontrado. Mensagem não enviada.".format(destinatario))

    async def buscar_usuario(self,comandos):
        #verificar número correto de argumentos
        if len(comandos)==2:
            await self.servidor.buscar_usuario(self,comandos[1])
        else:
            await self.envia("Comando inválido. Busque no formato: /buscar nome_desejado")
        
    async def listar_usuarios(self):
        await self.servidor.listar_usuarios(self)


servidor=Servidor()
loop=asyncio.get_event_loop()

start_server = websockets.serve(servidor.conecta, 'localhost', 50007)

try:
    loop.run_until_complete(start_server)
    loop.run_forever()
finally:
    start_server.close()