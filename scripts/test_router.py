from app.ai.router import route_message
for s in ['Paguei 25 reais no Uber','Quero comprar uma cafeteira de até 500 reais','Quero ir a um restaurante japonês','Agendar cinema sábado às 20h','Toda semana precisamos limpar a cozinha']:
    d=route_message(s); print(s,'->',d.destination,d.confidence)
