import rlcard
from rlcard.agents import RandomAgent

def iniciar_mesa_limit(agente_0, agente_1, renderizar_console=True):
    """
    Motor modular do Limit Texas Hold'em.
    Recebe dois agentes externos e executa a partida.
    """
    # 1. Instanciar ambiente
    env = rlcard.make('limit-holdem')
    
    # 2. Plugar os agentes recebidos como parâmetro
    env.set_agents([agente_0, agente_1])
    
    # 3. Iniciar rodada
    state, player_id = env.reset()
    
    if renderizar_console:
        print("="*50)
        print(" INICIANDO PARTIDA LIMIT HOLD'EM (MODULAR) ")
        print("="*50)

    # 4. Loop de execução do jogo
    while not env.is_over():
        # O agente da vez toma a decisão baseada no estado atual
        action = env.agents[player_id].step(state)
        
        if renderizar_console:
            acao_texto = str(env._decode_action(action)).replace('Action.', '').upper()
            cartas_mao = state['raw_obs'].get('hand', [])
            cartas_mesa = state['raw_obs'].get('public_cards', [])
            
            print(f"Vez do Jogador {player_id}")
            print(f"Mão: {cartas_mao}")
            print(f"Mesa: {cartas_mesa}")
            print(f"Ação: {acao_texto}")
            print("-" * 35)
            
        # Motor avança para o próximo estado
        state, player_id = env.step(action)
        
    # 5. Retorno dos resultados (Payoffs)
    payoffs = env.get_payoffs()
    
    if renderizar_console:
        print("\n--- FIM DE JOGO ---")
        print(f"Resultado (Fichas ganhas/perdidas):\nJogador 0: {payoffs[0]}\nJogador 1: {payoffs[1]}")
        
    return payoffs

if __name__ == '__main__':
    # Teste de integração: Instanciando agentes aleatórios e injetando na mesa
    agente_teste_A = RandomAgent(num_actions=4)
    agente_teste_B = RandomAgent(num_actions=4)
    
    iniciar_mesa_limit(agente_0=agente_teste_A, agente_1=agente_teste_B)