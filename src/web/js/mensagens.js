/* Orientações comuns para falhas de comunicação e respostas inesperadas. */
function mensagemErroAmigavel(erro, alternativa) {
    const texto = typeof erro === 'string' ? erro : erro?.message;
    const padrao = alternativa || 'Não foi possível concluir esta ação. Tente novamente. Se continuar, peça ajuda à equipe responsável pelo aplicativo.';
    if (!texto || /cannot import|traceback|sqlalchemy|sqlite|https?:\/\/|[a-z]:[\\/]|no module|has no attribute|invalid literal|could not convert|unsupported operand|unexpected keyword|src\.|TypeError|ReferenceError|SyntaxError|SELECT |INSERT |connectionpool/i.test(texto)) return padrao;
    if (/failed to fetch|networkerror|websocket|backend|connection refused|timed out|timeout/i.test(texto)) return 'A conexão foi interrompida ou demorou para responder. Verifique sua conexão e tente novamente. Se o aplicativo não responder, feche e abra novamente.';
    return texto;
}
