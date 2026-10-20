def get_move(board, player, history):
    for r in range(9):
        for c in range(9):
            cell = board[r][c]
            if cell and cell.get('player') == player:
                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 9 and 0 <= nc < 9:
                        dest = board[nr][nc]
                        if not dest:
                            return ((r, c), (nr, nc))
    return ((0,0),(0,0))
