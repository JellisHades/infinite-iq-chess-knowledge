import pygame
import chess
import random
import threading
from stockfish import Stockfish
import sys
from os.path import join
import json

pygame.mixer.init()
pygame.font.init()
pygame.init()

ProjectPath = "C:\\Users\\Windows\\OneDrive\\Desktop\\Projects\\ChessAnalyzer"
AssetsPath = join(ProjectPath, "Assets")
PremovesPath = join(AssetsPath, "Premoves.json")

StockfishParams = json.load(open(join(AssetsPath, "StockfishParams.json"), "r"))

EngineDepth = StockfishParams["depth"]
del StockfishParams["depth"]

BotDepth = StockfishParams["botdepth"]
del StockfishParams["botdepth"]

stockfish = Stockfish(
	path=join(ProjectPath, "stockfish\\stockfish-windows-x86-64-avx2.exe"), 
	depth=EngineDepth,
	parameters=StockfishParams
)

PieceImages = {
	"p": pygame.image.load(join(AssetsPath, 'bp.png')), 
	"P": pygame.image.load(join(AssetsPath, 'wp.png')),

	"k": pygame.image.load(join(AssetsPath, 'bk.png')), 
	"K": pygame.image.load(join(AssetsPath, 'wk.png')),

	"r": pygame.image.load(join(AssetsPath, 'br.png')), 
	"R": pygame.image.load(join(AssetsPath, 'wr.png')),

	"b": pygame.image.load(join(AssetsPath, 'bb.png')), 
	"B": pygame.image.load(join(AssetsPath, 'wb.png')),
		
	"q": pygame.image.load(join(AssetsPath, 'bq.png')),
	"Q": pygame.image.load(join(AssetsPath, 'wq.png')),

	"n": pygame.image.load(join(AssetsPath, 'bn.png')),
	"N": pygame.image.load(join(AssetsPath, 'wn.png'))
}

Sounds = {
	"move": join(AssetsPath, 'move.mp3'),
	"promote": join(AssetsPath, 'promote.mp3'),
	"check": join(AssetsPath, 'move-check.mp3'),
	"castle": join(AssetsPath, 'castle.mp3'),
	"capture": join(AssetsPath, 'capture.mp3'),
	"end": join(AssetsPath, 'game-end.mp3'),
}

for Index in Sounds:
	Sounds[Index] = pygame.mixer.Sound(Sounds[Index])

pygame.display.set_caption("Chess")
pygame.display.set_icon(pygame.image.load(join(AssetsPath, "Icon.jpg")))

DefaultFont = pygame.font.SysFont('Source Sans Pro', 40)

Width = 600
BoardSize = 8
PieceWidth = int(Width / BoardSize)
Window = pygame.display.set_mode((Width, Width), pygame.RESIZABLE)

PromotionOrder = ["q", "n", "r", "b"]

def PlaySound(SoundObject): SoundObject.play()

def IndexToPos(Index):
	Index = Index + 1
	Y = int((Index - 1) / BoardSize) + 1
	X = (Index) - ((Y - 1) * BoardSize)

	X = Team and X or (-X + (BoardSize + 1))
	Y = Team and (-Y + (BoardSize + 1)) or Y

	return (X, Y)

def PosToIndex(pos):
	X, Y = pos

	X = Team and X or (-X + (BoardSize + 1))
	Y = Team and (-Y + (BoardSize + 1)) or Y

	return (((Y - 1) * BoardSize) + X) - 1

def FindIndex(pos):
	Interval = Width / BoardSize
	x, y = pos

	Index = PosToIndex((int(x // Interval) + 1, int(y // Interval) + 1))
	return Index #Team and Index or (-Index + ((BoardSize * BoardSize) - 1))

def PosToNotation(pos):
	return [
		"a",
		"b",
		"c",
		"d",
		"e",
		"f",
		"g",
		"h"
	][(Team and pos[0] - 1) or (not Team and -pos[0] + 8)] + str(Team and -pos[1] + 9 or pos[1])

def NotationToPos(Notation):
	X = {
		"a": 1,
		"b": 2,
		"c": 3,
		"d": 4,
		"e": 5,
		"f": 6,
		"g": 7,
		"h": 8
	}[Notation[0]]

	return (Team and X or (-X + 9), Team and -int(Notation[1]) + 9 or int(Notation[1]))

def GetResizedPiece(PieceImage):
	return pygame.transform.scale(
		PieceImage, 
		(PieceWidth, PieceWidth)
	)

while True:
	board = chess.Board()

	Team = random.random() > 0.5
	PromotionSquare = None
	PromotionStart = None

	LastFENPos = board.board_fen()

	FreezeFinding = False
	CurrentBestMove = None
	BotMove = None

	SelectedPiece = None
	LastMove = None
	Mover = True

	MoveHints = []
	
	ChosenMove = None
	RestartBounds = None

	GameRunning = True
	Moves = 0
	MaxMoveSave = 20

	def DisplayGrid():
		StartX, StartY, EndX, EndY = None, None, None, None

		if LastMove:
			StartX, StartY = NotationToPos(LastMove[:2])
			EndX, EndY = NotationToPos(LastMove[2:])

		for i in range(BoardSize):
			for j in range(BoardSize):
				pygame.draw.rect(
					Window, 
					(i + j) % 2 == 0 and "#EBECD0" or "#739552",
					pygame.Rect(
						Width * (i / BoardSize), 
						Width * (j / BoardSize), 
						PieceWidth, PieceWidth
					)
				)

				if LastMove and ((i + 1) == StartX and (j + 1) == StartY) or ((i + 1) == EndX and (j + 1) == EndY):
					Surface = pygame.Surface((PieceWidth, PieceWidth), pygame.SRCALPHA)  
					Surface.fill((255, 255, 51, int(255 / 2)))
					
					Window.blit(Surface, (Width * (i / BoardSize), Width * (j / BoardSize)))

	def DisplayPieces():
		global Mover, MoveHints, Surface

		for Index in range((BoardSize * BoardSize)):
			X, Y = IndexToPos(Index)

			PieceOnPos = str(board.piece_at(Index))
			if PieceOnPos == "None": continue

			Window.blit(GetResizedPiece(PieceImages[PieceOnPos]), (
				((X - 1) / BoardSize) * Width, 
				((Y - 1) / BoardSize) * Width
			))

		MoveHints = []

		if SelectedPiece != None and Mover == Team:
			PosNotation = PosToNotation(IndexToPos(SelectedPiece))
			LegalMoves = list(board.legal_moves)
			
			for Move in LegalMoves:
				if Move.uci()[:2] == PosNotation:
					X, Y = NotationToPos(Move.uci()[2:])

					MoveHints.append(Move)
					Surface = pygame.Surface((PieceWidth, PieceWidth), pygame.SRCALPHA)

					pygame.draw.circle(
						Surface, 
						(0, 0, 0, 255 * .14), 
						(PieceWidth * 0.5, PieceWidth * 0.5),
						(PieceWidth * (1 / 3)) * 0.5
					)
					
					Window.blit(Surface, (((X - 1) / BoardSize) * Width, ((Y - 1) / BoardSize) * Width))

		if PromotionSquare:
			pygame.draw.rect(
				Window, (255, 255, 255), pygame.Rect(
				(PromotionSquare[0] - 1) * PieceWidth, (PromotionSquare[1] - 1) * PieceWidth, 
				PieceWidth, PieceWidth * 4
				)
			)

			for i in range(len(PromotionOrder)):
				Window.blit(GetResizedPiece(PieceImages[Team and PromotionOrder[i].upper() or PromotionOrder[i]]), (
					(PromotionSquare[0] - 1) * PieceWidth, 
					((PromotionSquare[1] - 1) * PieceWidth) + ((i) * PieceWidth), 
				))

	def GetRandomMove():
		global BotMove, FreezeFinding

		LegalMoves = list(board.legal_moves)
		random.shuffle(LegalMoves)

		if len(LegalMoves) <= 0: return

		if random.random() < 0.4:
			BotMove = str(LegalMoves[0])
			return

		BotMove = None
		FreezeFinding = True
		stockfish.set_fen_position(board.fen())
		stockfish.set_depth(BotDepth)

		BotMoves = stockfish.get_top_moves(min(5, len(LegalMoves)))
		random.shuffle(BotMoves)

		BotMove = BotMoves[0]["Move"]

		FreezeFinding = False

	def ChangeBestMove(FEN):
		global CurrentBestMove, FreezeFinding

		PremovesFile = open(PremovesPath, "r+")
		Premoves = json.loads(PremovesFile.read())

		if FEN in Premoves:
			CurrentBestMove = Premoves[FEN]
			return
		
		CurrentBestMove = None
		FreezeFinding = True

		stockfish.set_fen_position(FEN)
		stockfish.set_depth(EngineDepth)
		CurrentBestMove = stockfish.get_best_move()
		FreezeFinding = False

		Premoves[FEN] = CurrentBestMove
		PremovesFile.seek(0)
		PremovesFile.write(json.dumps(Premoves))
		PremovesFile.truncate()
	
	def PushMove(MoveChosen):
		global LastMove, Mover, PromotionStart, PromotionSquare, SelectedPiece, ChosenMove, LastFENPos, Moves
		LastFENPos = board.fen()

		PlayingSound = Sounds["move"]
		
		if board.is_capture(MoveChosen):
			PlayingSound = Sounds["capture"]
		if board.is_castling(MoveChosen):
			PlayingSound = Sounds["castle"]
		if len(str(MoveChosen)) > 4:
			PlayingSound = Sounds["castle"]

		Moves += 1
		board.push(MoveChosen)
		
		if board.is_check():
			PlayingSound = Sounds["check"]
		elif board.is_game_over():
			PlayingSound = Sounds["end"]

		threading.Thread(target=PlaySound, args=(PlayingSound,)).start()

		ChosenMove = str(MoveChosen)
		LastMove = str(MoveChosen)
						
		SelectedPiece = None
		PromotionSquare = None
		PromotionStart = None

		Mover = not Mover

		if Mover == Team and not FreezeFinding:
			threading.Thread(target=ChangeBestMove, args=(board.fen(),)).start()

	while GameRunning:
		DisplayGrid()
		DisplayPieces()
		pygame.time.delay(50) 

		for Event in pygame.event.get():
			if Event.type == pygame.QUIT:
				pygame.quit()
				sys.exit()

			if Event.type == pygame.VIDEORESIZE:
				Width = round(Event.w / BoardSize) * BoardSize
				PieceWidth = int(Width / BoardSize)
				Window = pygame.display.set_mode((Width, Width), pygame.RESIZABLE)

			if Event.type == pygame.MOUSEBUTTONDOWN:
				MousePos = pygame.mouse.get_pos()

				if RestartBounds:
					if RestartBounds.collidepoint(MousePos):
						GameRunning = False
						break
					continue

				Index = FindIndex(MousePos)

				if Index < 0 or Index > 63:
					continue

				PieceOnPos = str(board.piece_at(chess.SQUARES[Index]))

				if PromotionSquare:
					IndexPos = IndexToPos(Index)
					
					if IndexPos[1] >= 0 and IndexPos[1] < len(PromotionOrder) + 1 and IndexPos[0] == PromotionSquare[0]:
						PushMove(chess.Move.from_uci(PosToNotation(PromotionStart) + PosToNotation(PromotionSquare) + (PromotionOrder[IndexPos[1] - PromotionSquare[1]])))
						continue
				
				PromotionSquare = None
				PromotionStart = None

				if SelectedPiece != None:
					for MoveHint in MoveHints:
						Start = str(MoveHint)[:2]
						NewPos = str(MoveHint)[2:4]

						if NewPos == PosToNotation(IndexToPos(Index)) and Start == PosToNotation(IndexToPos(SelectedPiece)):
							if len(str(MoveHint)) > 4:
								PromotionSquare = NotationToPos(NewPos)
								PromotionStart = NotationToPos(Start)
							else:
								PushMove(MoveHint)

				if PieceOnPos == "None" or PieceOnPos.isupper() != Team:
					SelectedPiece = None
					continue

				SelectedPiece = Index

		if Mover != Team and not FreezeFinding:
			if ChosenMove and not CurrentBestMove:
				threading.Thread(target=ChangeBestMove, args=(LastFENPos,)).start()

			if RestartBounds or (ChosenMove and CurrentBestMove and CurrentBestMove != ChosenMove):
				Text = DefaultFont.render(f'{CurrentBestMove} is best', False, (0, 0, 0))

				StartX, StartY = NotationToPos(CurrentBestMove[:2])
				EndX, EndY = NotationToPos(CurrentBestMove[2:])

				Surface = pygame.Surface((PieceWidth, PieceWidth), pygame.SRCALPHA)  
				Surface.fill((3, 144, 252, int(255 / 2)))

				Window.blit(Surface, ((StartX - 1) * PieceWidth, (StartY - 1) * PieceWidth))
				Window.blit(Surface, ((EndX - 1) * PieceWidth, (EndY - 1) * PieceWidth))
				
				Window.blit(Text, Text.get_rect(center=(Width/2, Width/2)))
				RestartBounds = Text.get_rect(center=(Width/2, Width/2))
			elif (not Team and Moves == 0) or (ChosenMove and CurrentBestMove):
				if not BotMove:
					threading.Thread(target=GetRandomMove).start()
				else:
					PushMove(chess.Move.from_uci(BotMove))
					CurrentBestMove = None
					BotMove = None

		pygame.display.update()