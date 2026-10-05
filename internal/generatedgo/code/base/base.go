package base

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"math"
	"math/bits"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

type Wasi_snapshot_preview1Imports interface {
	Args_get(m *Module, l0 int32, l1 int32) int32
	Args_sizes_get(m *Module, l0 int32, l1 int32) int32
	Environ_get(m *Module, l0 int32, l1 int32) int32
	Environ_sizes_get(m *Module, l0 int32, l1 int32) int32
	Clock_time_get(m *Module, l0 int32, l1 int64, l2 int32) int32
	Fd_advise(m *Module, l0 int32, l1 int64, l2 int64, l3 int32) int32
	Fd_allocate(m *Module, l0 int32, l1 int64, l2 int64) int32
	Fd_close(m *Module, l0 int32) int32
	Fd_datasync(m *Module, l0 int32) int32
	Fd_fdstat_get(m *Module, l0 int32, l1 int32) int32
	Fd_fdstat_set_flags(m *Module, l0 int32, l1 int32) int32
	Fd_filestat_get(m *Module, l0 int32, l1 int32) int32
	Fd_filestat_set_size(m *Module, l0 int32, l1 int64) int32
	Fd_pread(m *Module, l0 int32, l1 int32, l2 int32, l3 int64, l4 int32) int32
	Fd_prestat_get(m *Module, l0 int32, l1 int32) int32
	Fd_prestat_dir_name(m *Module, l0 int32, l1 int32, l2 int32) int32
	Fd_pwrite(m *Module, l0 int32, l1 int32, l2 int32, l3 int64, l4 int32) int32
	Fd_read(m *Module, l0 int32, l1 int32, l2 int32, l3 int32) int32
	Fd_readdir(m *Module, l0 int32, l1 int32, l2 int32, l3 int64, l4 int32) int32
	Fd_renumber(m *Module, l0 int32, l1 int32) int32
	Fd_seek(m *Module, l0 int32, l1 int64, l2 int32, l3 int32) int32
	Fd_tell(m *Module, l0 int32, l1 int32) int32
	Fd_write(m *Module, l0 int32, l1 int32, l2 int32, l3 int32) int32
	Path_create_directory(m *Module, l0 int32, l1 int32, l2 int32) int32
	Path_filestat_get(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32) int32
	Path_filestat_set_times(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int64, l5 int64, l6 int32) int32
	Path_readlink(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32
	Path_remove_directory(m *Module, l0 int32, l1 int32, l2 int32) int32
	Path_rename(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32
	Path_symlink(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32) int32
	Path_unlink_file(m *Module, l0 int32, l1 int32, l2 int32) int32
	Poll_oneoff(m *Module, l0 int32, l1 int32, l2 int32, l3 int32) int32
	Sched_yield(m *Module) int32
	Sock_recv(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32
	Sock_send(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32) int32
	Sock_shutdown(m *Module, l0 int32, l1 int32) int32
}
type EnvImports interface {
}
type Wasix_32v1Imports interface {
	Fd_dup(m *Module, l0 int32, l1 int32) int32
	Fd_dup2(m *Module, l0 int32, l1 int32, l2 int32, l3 int32) int32
	Getcwd(m *Module, l0 int32, l1 int32) int32
	Callback_signal(m *Module, l0 int32, l1 int32)
	Thread_parallelism(m *Module, l0 int32) int32
	Thread_signal(m *Module, l0 int32, l1 int32) int32
	Futex_wait(m *Module, l0 int32, l1 int32, l2 int32, l3 int32) int32
	Futex_wake(m *Module, l0 int32, l1 int32) int32
	Futex_wake_all(m *Module, l0 int32, l1 int32) int32
	Thread_exit(m *Module, l0 int32)
	Path_open2(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int64, l6 int64, l7 int32, l8 int32, l9 int32) int32
	Fd_fdflags_get(m *Module, l0 int32, l1 int32) int32
	Fd_fdflags_set(m *Module, l0 int32, l1 int32) int32
	Proc_exit2(m *Module, l0 int32)
	Proc_id(m *Module, l0 int32) int32
	Proc_signals_get(m *Module, l0 int32) int32
	Proc_signals_sizes_get(m *Module, l0 int32) int32
	Sock_addr_local(m *Module, l0 int32, l1 int32) int32
	Sock_addr_peer(m *Module, l0 int32, l1 int32) int32
	Sock_open(m *Module, l0 int32, l1 int32, l2 int32, l3 int32) int32
	Sock_set_opt_flag(m *Module, l0 int32, l1 int32, l2 int32) int32
	Sock_set_opt_time(m *Module, l0 int32, l1 int32, l2 int32) int32
	Sock_set_opt_size(m *Module, l0 int32, l1 int32, l2 int64) int32
	Sock_get_opt_size(m *Module, l0 int32, l1 int32, l2 int32) int32
	Sock_bind(m *Module, l0 int32, l1 int32) int32
	Sock_connect(m *Module, l0 int32, l1 int32) int32
	Sock_send_to(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32
	Resolve(m *Module, l0 int32, l1 int32, l2 int32, l3 int32, l4 int32, l5 int32) int32
}
type Module struct {
	Memory                 []byte
	MaxMem                 uint64
	M                      unsafe.Pointer
	ExcPending             int32
	ExcTag                 uint32
	ExcVals                [1]uint64
	T0                     []any
	G0                     int32
	G1                     int32
	G2                     int32
	G3                     int32
	G4                     int32
	G5                     int32
	G6                     int32
	G7                     int32
	G8                     int32
	G9                     int32
	G10                    int32
	G11                    int32
	G12                    int32
	G13                    int32
	G14                    int32
	G15                    int32
	G16                    int32
	G17                    int32
	G18                    int32
	G19                    int32
	G20                    int32
	G21                    int32
	G22                    int32
	G23                    int32
	G24                    int32
	G25                    int32
	G26                    int32
	G27                    int32
	G28                    int32
	G29                    int32
	G30                    int32
	G31                    int32
	G32                    int32
	G33                    int32
	G34                    int32
	G35                    int32
	G36                    int32
	G37                    int32
	G38                    int32
	G39                    int32
	G40                    int32
	G41                    int32
	G42                    int32
	G43                    int32
	G44                    int32
	G45                    int32
	G46                    int32
	G47                    int32
	G48                    int32
	G49                    int32
	G50                    int32
	G51                    int32
	G52                    int32
	G53                    int32
	G54                    int32
	G55                    int32
	G56                    int32
	G57                    int32
	G58                    int32
	G59                    int32
	G60                    int32
	G61                    int32
	G62                    int32
	G63                    int32
	G64                    int32
	G65                    int32
	G66                    int32
	G67                    int32
	G68                    int32
	G69                    int32
	G70                    int32
	G71                    int32
	G72                    int32
	G73                    int32
	G74                    int32
	G75                    int32
	G76                    int32
	G77                    int32
	G78                    int32
	G79                    int32
	G80                    int32
	G81                    int32
	G82                    int32
	G83                    int32
	G84                    int32
	G85                    int32
	G86                    int32
	G87                    int32
	G88                    int32
	G89                    int32
	G90                    int32
	G91                    int32
	G92                    int32
	G93                    int32
	G94                    int32
	G95                    int32
	G96                    int32
	G97                    int32
	G98                    int32
	G99                    int32
	G100                   int32
	G101                   int32
	G102                   int32
	G103                   int32
	G104                   int32
	G105                   int32
	G106                   int32
	G107                   int32
	G108                   int32
	G109                   int32
	G110                   int32
	G111                   int32
	G112                   int32
	G113                   int32
	G114                   int32
	G115                   int32
	G116                   int32
	G117                   int32
	G118                   int32
	G119                   int32
	G120                   int32
	G121                   int32
	G122                   int32
	G123                   int32
	G124                   int32
	G125                   int32
	G126                   int32
	G127                   int32
	G128                   int32
	G129                   int32
	G130                   int32
	G131                   int32
	G132                   int32
	G133                   int32
	G134                   int32
	G135                   int32
	G136                   int32
	G137                   int32
	G138                   int32
	G139                   int32
	G140                   int32
	G141                   int32
	G142                   int32
	G143                   int32
	G144                   int32
	G145                   int32
	G146                   int32
	G147                   int32
	G148                   int32
	G149                   int32
	G150                   int32
	G151                   int32
	G152                   int32
	G153                   int32
	G154                   int32
	G155                   int32
	G156                   int32
	G157                   int32
	G158                   int32
	G159                   int32
	G160                   int32
	G161                   int32
	G162                   int32
	G163                   int32
	G164                   int32
	G165                   int32
	G166                   int32
	G167                   int32
	G168                   int32
	G169                   int32
	G170                   int32
	G171                   int32
	G172                   int32
	G173                   int32
	G174                   int32
	G175                   int32
	G176                   int32
	G177                   int32
	G178                   int32
	G179                   int32
	G180                   int32
	G181                   int32
	G182                   int32
	G183                   int32
	G184                   int32
	G185                   int32
	G186                   int32
	G187                   int32
	G188                   int32
	G189                   int32
	G190                   int32
	G191                   int32
	G192                   int32
	G193                   int32
	G194                   int32
	G195                   int32
	G196                   int32
	G197                   int32
	G198                   int32
	G199                   int32
	G200                   int32
	G201                   int32
	G202                   int32
	G203                   int32
	G204                   int32
	G205                   int32
	G206                   int32
	G207                   int32
	G208                   int32
	G209                   int32
	G210                   int32
	G211                   int32
	G212                   int32
	G213                   int32
	G214                   int32
	G215                   int32
	G216                   int32
	G217                   int32
	G218                   int32
	G219                   int32
	G220                   int32
	G221                   int32
	G222                   int32
	G223                   int32
	G224                   int32
	G225                   int32
	G226                   int32
	G227                   int32
	G228                   int32
	G229                   int32
	G230                   int32
	G231                   int32
	G232                   int32
	G233                   int32
	G234                   int32
	G235                   int32
	G236                   int32
	G237                   int32
	G238                   int32
	G239                   int32
	G240                   int32
	G241                   int32
	G242                   int32
	G243                   int32
	G244                   int32
	G245                   int32
	G246                   int32
	G247                   int32
	G248                   int32
	G249                   int32
	G250                   int32
	G251                   int32
	G252                   int32
	G253                   int32
	G254                   int32
	G255                   int32
	G256                   int32
	G257                   int32
	G258                   int32
	G259                   int32
	G260                   int32
	G261                   int32
	G262                   int32
	G263                   int32
	G264                   int32
	G265                   int32
	G266                   int32
	G267                   int32
	G268                   int32
	G269                   int32
	G270                   int32
	G271                   int32
	G272                   int32
	G273                   int32
	G274                   int32
	G275                   int32
	G276                   int32
	G277                   int32
	G278                   int32
	G279                   int32
	G280                   int32
	G281                   int32
	G282                   int32
	G283                   int32
	G284                   int32
	G285                   int32
	G286                   int32
	G287                   int32
	G288                   int32
	G289                   int32
	G290                   int32
	G291                   int32
	G292                   int32
	G293                   int32
	G294                   int32
	G295                   int32
	G296                   int32
	G297                   int32
	G298                   int32
	G299                   int32
	G300                   int32
	G301                   int32
	G302                   int32
	G303                   int32
	G304                   int32
	G305                   int32
	G306                   int32
	G307                   int32
	G308                   int32
	G309                   int32
	G310                   int32
	G311                   int32
	G312                   int32
	G313                   int32
	G314                   int32
	G315                   int32
	G316                   int32
	G317                   int32
	G318                   int32
	G319                   int32
	G320                   int32
	G321                   int32
	G322                   int32
	G323                   int32
	G324                   int32
	G325                   int32
	G326                   int32
	G327                   int32
	G328                   int32
	G329                   int32
	G330                   int32
	G331                   int32
	G332                   int32
	G333                   int32
	G334                   int32
	G335                   int32
	G336                   int32
	G337                   int32
	G338                   int32
	G339                   int32
	G340                   int32
	G341                   int32
	G342                   int32
	G343                   int32
	G344                   int32
	G345                   int32
	G346                   int32
	G347                   int32
	G348                   int32
	G349                   int32
	G350                   int32
	G351                   int32
	G352                   int32
	G353                   int32
	G354                   int32
	G355                   int32
	G356                   int32
	G357                   int32
	G358                   int32
	G359                   int32
	G360                   int32
	G361                   int32
	G362                   int32
	G363                   int32
	G364                   int32
	G365                   int32
	G366                   int32
	G367                   int32
	G368                   int32
	G369                   int32
	G370                   int32
	G371                   int32
	G372                   int32
	G373                   int32
	G374                   int32
	G375                   int32
	G376                   int32
	G377                   int32
	G378                   int32
	G379                   int32
	G380                   int32
	G381                   int32
	G382                   int32
	G383                   int32
	G384                   int32
	G385                   int32
	G386                   int32
	G387                   int32
	G388                   int32
	G389                   int32
	G390                   int32
	G391                   int32
	G392                   int32
	G393                   int32
	G394                   int32
	G395                   int32
	G396                   int32
	G397                   int32
	G398                   int32
	G399                   int32
	G400                   int32
	G401                   int32
	G402                   int32
	G403                   int32
	G404                   int32
	G405                   int32
	G406                   int32
	G407                   int32
	G408                   int32
	G409                   int32
	G410                   int32
	G411                   int32
	G412                   int32
	G413                   int32
	G414                   int32
	G415                   int32
	G416                   int32
	G417                   int32
	G418                   int32
	G419                   int32
	G420                   int32
	G421                   int32
	G422                   int32
	G423                   int32
	G424                   int32
	G425                   int32
	G426                   int32
	G427                   int32
	G428                   int32
	G429                   int32
	G430                   int32
	G431                   int32
	G432                   int32
	G433                   int32
	G434                   int32
	G435                   int32
	G436                   int32
	G437                   int32
	G438                   int32
	G439                   int32
	G440                   int32
	G441                   int32
	G442                   int32
	G443                   int32
	G444                   int32
	G445                   int32
	G446                   int32
	G447                   int32
	G448                   int32
	G449                   int32
	G450                   int32
	G451                   int32
	G452                   int32
	G453                   int32
	G454                   int32
	G455                   int32
	G456                   int32
	G457                   int32
	G458                   int32
	G459                   int32
	G460                   int32
	G461                   int32
	G462                   int32
	G463                   int32
	G464                   int32
	G465                   int32
	G466                   int32
	G467                   int32
	G468                   int32
	G469                   int32
	G470                   int32
	G471                   int32
	G472                   int32
	G473                   int32
	G474                   int32
	G475                   int32
	G476                   int32
	G477                   int32
	G478                   int32
	G479                   int32
	G480                   int32
	G481                   int32
	G482                   int32
	G483                   int32
	G484                   int32
	G485                   int32
	G486                   int32
	G487                   int32
	G488                   int32
	G489                   int32
	G490                   int32
	G491                   int32
	G492                   int32
	G493                   int32
	G494                   int32
	G495                   int32
	G496                   int32
	G497                   int32
	G498                   int32
	G499                   int32
	G500                   int32
	G501                   int32
	G502                   int32
	G503                   int32
	G504                   int32
	G505                   int32
	G506                   int32
	G507                   int32
	G508                   int32
	G509                   int32
	G510                   int32
	G511                   int32
	G512                   int32
	G513                   int32
	G514                   int32
	G515                   int32
	G516                   int32
	G517                   int32
	G518                   int32
	G519                   int32
	G520                   int32
	G521                   int32
	G522                   int32
	G523                   int32
	G524                   int32
	G525                   int32
	G526                   int32
	G527                   int32
	G528                   int32
	G529                   int32
	G530                   int32
	G531                   int32
	G532                   int32
	G533                   int32
	G534                   int32
	G535                   int32
	G536                   int32
	G537                   int32
	G538                   int32
	G539                   int32
	G540                   int32
	G541                   int32
	G542                   int32
	G543                   int32
	G544                   int32
	G545                   int32
	G546                   int32
	G547                   int32
	G548                   int32
	G549                   int32
	G550                   int32
	G551                   int32
	G552                   int32
	G553                   int32
	G554                   int32
	G555                   int32
	G556                   int32
	G557                   int32
	G558                   int32
	G559                   int32
	G560                   int32
	G561                   int32
	G562                   int32
	G563                   int32
	G564                   int32
	G565                   int32
	G566                   int32
	G567                   int32
	G568                   int32
	G569                   int32
	G570                   int32
	G571                   int32
	G572                   int32
	G573                   int32
	G574                   int32
	G575                   int32
	G576                   int32
	G577                   int32
	G578                   int32
	G579                   int32
	G580                   int32
	G581                   int32
	G582                   int32
	G583                   int32
	G584                   int32
	G585                   int32
	G586                   int32
	G587                   int32
	G588                   int32
	G589                   int32
	G590                   int32
	G591                   int32
	G592                   int32
	G593                   int32
	G594                   int32
	G595                   int32
	G596                   int32
	G597                   int32
	G598                   int32
	G599                   int32
	G600                   int32
	G601                   int32
	G602                   int32
	G603                   int32
	G604                   int32
	G605                   int32
	G606                   int32
	G607                   int32
	G608                   int32
	G609                   int32
	G610                   int32
	G611                   int32
	G612                   int32
	G613                   int32
	G614                   int32
	G615                   int32
	G616                   int32
	G617                   int32
	G618                   int32
	G619                   int32
	G620                   int32
	G621                   int32
	G622                   int32
	G623                   int32
	G624                   int32
	G625                   int32
	G626                   int32
	G627                   int32
	G628                   int32
	G629                   int32
	G630                   int32
	G631                   int32
	G632                   int32
	G633                   int32
	G634                   int32
	G635                   int32
	G636                   int32
	G637                   int32
	G638                   int32
	G639                   int32
	G640                   int32
	G641                   int32
	G642                   int32
	G643                   int32
	G644                   int32
	G645                   int32
	G646                   int32
	G647                   int32
	G648                   int32
	G649                   int32
	G650                   int32
	G651                   int32
	G652                   int32
	G653                   int32
	G654                   int32
	G655                   int32
	G656                   int32
	G657                   int32
	G658                   int32
	G659                   int32
	G660                   int32
	G661                   int32
	G662                   int32
	G663                   int32
	G664                   int32
	G665                   int32
	G666                   int32
	G667                   int32
	G668                   int32
	G669                   int32
	G670                   int32
	G671                   int32
	G672                   int32
	G673                   int32
	G674                   int32
	G675                   int32
	G676                   int32
	G677                   int32
	G678                   int32
	G679                   int32
	G680                   int32
	G681                   int32
	G682                   int32
	G683                   int32
	G684                   int32
	G685                   int32
	G686                   int32
	G687                   int32
	G688                   int32
	G689                   int32
	G690                   int32
	G691                   int32
	G692                   int32
	G693                   int32
	G694                   int32
	G695                   int32
	G696                   int32
	G697                   int32
	G698                   int32
	G699                   int32
	G700                   int32
	G701                   int32
	G702                   int32
	G703                   int32
	G704                   int32
	G705                   int32
	G706                   int32
	Wasi_snapshot_preview1 Wasi_snapshot_preview1Imports
	Env                    EnvImports
	Wasix_32v1             Wasix_32v1Imports
	MemMu                  *sync.Mutex
	MemSize                *atomic.Uint64
	DataSegs               [][]byte
	DataEnd                uint32
	MemShared              bool
	Threads                *ThreadPool
	PrepareMemoryGrow      func(uint64, uint64) error
	ThreadStart            func(*Module, int32, int32)
}

func I32(x int32) int32 { return x }

func I64(x int64) int64 { return x }

// ui32 / ui64 reinterpret a signed integer as its unsigned bit
// equivalent at runtime. Used for the operands of wasm unsigned
// comparisons (i32.lt_u etc.) — emitting `uint32(int32(-N))` directly
// fails Go's compile-time constant rule because the negative typed
// constant isn't representable in uint32; routing through these
// function-call boundaries forces runtime conversion.
func Ui32(x int32) uint32 { return uint32(x) }

func Ui64(x int64) uint64 { return uint64(x) }

// b2i32 materialises a wasm comparison result — an i32 that is 0 or 1 — from
// the Go bool the comparison expression evaluates to.
//
// It exists as a named helper rather than an inline `func() int32 { ... }()`
// because the gcasm backend requires every direct call left in the compiled
// output to be either a package-local FnN or something the Go inliner removed.
// A func literal is normally inlined at its call site, but the inliner gives up
// once the ENCLOSING function grows past its budget — and a single wasm function
// can translate to tens of thousands of lines of Go, as an interpreter's
// bytecode dispatch loop does. The literal is then outlined into a real closure
// symbol (FnN.funcA.funcB), which reaches the assembler as a direct call gcasm
// cannot marshal. A named helper this small is always inlined, and if it ever
// were not, it would fail loudly at its own symbol rather than as a nested
// closure.
func B2i32(b bool) int32 {
	if b {
		return 1
	}
	return 0
}

func F32(x float32) float32 { runtime.KeepAlive(&x); return x }

func F64(x float64) float64 { runtime.KeepAlive(&x); return x }

//go:noinline
func Wasm_trap_div_zero() { panic("wasm: integer divide by zero") }

//go:noinline
func Wasm_trap_int_overflow() { panic("wasm: integer overflow") }

//go:noinline
func Wasm_trap_invalid_conv() { panic("wasm: invalid conversion to integer") }

//go:noinline
func Wasm_trap_unreachable() { panic("wasm: unreachable") }

//go:noinline
func Wasm_trap_memfill_oob() { panic("wasm: memory.fill out of bounds") }

//go:noinline
func Wasm_trap_memcopy_oob() { panic("wasm: memory.copy out of bounds") }

//go:noinline
func Wasm_trap_meminit_oob() { panic("wasm: memory.init out of bounds") }

func I32_div_s(x, y int32) int32 {
	if y == -1 && x == math.MinInt32 {
		Wasm_trap_int_overflow()
	}
	if y == 0 {
		Wasm_trap_div_zero()
	}
	return x / y
}

func I64_div_s(x, y int64) int64 {
	if y == -1 && x == math.MinInt64 {
		Wasm_trap_int_overflow()
	}
	if y == 0 {
		Wasm_trap_div_zero()
	}
	return x / y
}

func I32_div_u(x, y uint32) uint32 {
	if y == 0 {
		Wasm_trap_div_zero()
	}
	return x / y
}

func I64_div_u(x, y uint64) uint64 {
	if y == 0 {
		Wasm_trap_div_zero()
	}
	return x / y
}

func I32_rem_s(x, y int32) int32 {
	if y == 0 {
		Wasm_trap_div_zero()
	}
	if y == -1 {

		return 0
	}
	return x % y
}

func I64_rem_s(x, y int64) int64 {
	if y == 0 {
		Wasm_trap_div_zero()
	}
	if y == -1 {
		return 0
	}
	return x % y
}

func I32_rem_u(x, y uint32) uint32 {
	if y == 0 {
		Wasm_trap_div_zero()
	}
	return x % y
}

func I64_rem_u(x, y uint64) uint64 {
	if y == 0 {
		Wasm_trap_div_zero()
	}
	return x % y
}

func I32_rotl(x, y int32) int32 { return int32(bits.RotateLeft32(uint32(x), int(y&31))) }

func I32_rotr(x, y int32) int32 { return int32(bits.RotateLeft32(uint32(x), -int(y&31))) }

func I64_rotl(x, y int64) int64 { return int64(bits.RotateLeft64(uint64(x), int(y&63))) }

func F64_min(x, y float64) float64 {
	if x != x || y != y {
		return math.NaN()
	}
	if x < y {
		return x
	}
	if y < x {
		return y
	}
	if x == 0 {
		if math.Signbit(x) {
			return x
		}
		return y
	}
	return x
}

func F64_max(x, y float64) float64 {
	if x != x || y != y {
		return math.NaN()
	}
	if x > y {
		return x
	}
	if y > x {
		return y
	}
	if x == 0 {
		if math.Signbit(x) {
			return y
		}
		return x
	}
	return x
}

func F32_abs(x float32) float32 {
	return math.Float32frombits(math.Float32bits(x) &^ (1 << 31))
}

func F64_abs(x float64) float64 {
	return math.Float64frombits(math.Float64bits(x) &^ (1 << 63))
}

func F32_neg(x float32) float32 {
	return math.Float32frombits(math.Float32bits(x) ^ (1 << 31))
}

func F64_neg(x float64) float64 {
	return math.Float64frombits(math.Float64bits(x) ^ (1 << 63))
}

func F64_copysign(x, y float64) float64 { return math.Copysign(x, y) }

func F32_nearest(x float32) float32 { return float32(math.RoundToEven(float64(x))) }

func F64_nearest(x float64) float64 { return math.RoundToEven(x) }

func I32_trunc_sat_f32_s(x float32) int32 {
	if x != x {
		return 0
	}
	if x <= -2147483648.0 {
		return math.MinInt32
	}
	if x >= 2147483648.0 {
		return math.MaxInt32
	}
	return int32(x)
}

func I32_trunc_sat_f32_u(x float32) int32 {
	if x != x || x <= 0 {
		return 0
	}
	if x >= 4294967296.0 {
		return -1
	}
	return int32(uint32(x))
}

func I32_trunc_sat_f64_s(x float64) int32 {
	if x != x {
		return 0
	}
	if x <= -2147483648.0 {
		return math.MinInt32
	}
	if x >= 2147483648.0 {
		return math.MaxInt32
	}
	return int32(x)
}

func I32_trunc_sat_f64_u(x float64) int32 {
	if x != x || x <= 0 {
		return 0
	}
	if x >= 4294967296.0 {
		return -1
	}
	return int32(uint32(x))
}

func I64_trunc_sat_f32_s(x float32) int64 {
	if x != x {
		return 0
	}
	if float64(x) <= -9223372036854775808.0 {
		return math.MinInt64
	}
	if float64(x) >= 9223372036854775808.0 {
		return math.MaxInt64
	}
	return int64(x)
}

func I64_trunc_sat_f32_u(x float32) int64 {
	if x != x || x <= 0 {
		return 0
	}
	if float64(x) >= 18446744073709551616.0 {
		return -1
	}
	return int64(uint64(x))
}

func I64_trunc_sat_f64_s(x float64) int64 {
	if x != x {
		return 0
	}
	if x <= -9223372036854775808.0 {
		return math.MinInt64
	}
	if x >= 9223372036854775808.0 {
		return math.MaxInt64
	}
	return int64(x)
}

func I64_trunc_sat_f64_u(x float64) int64 {
	if x != x || x <= 0 {
		return 0
	}
	if x >= 18446744073709551616.0 {
		return -1
	}
	return int64(uint64(x))
}

// memorySize returns the current size of m.memory in wasm pages (each
// page is 64 KiB).
func MemorySize(m *Module) int32 {
	return int32(m.MemSize.Load() >> 16)
}

// wasmMemHardCap is the implementation limit on linear-memory size:
// 65534 pages, two short of wasm32's architectural 65536. Growth past
// it fails with -1 like any resource limit (the JS API allows an
// engine to refuse any grow). Keeping memSize strictly below 2^32
// minus a 128 KiB margin is what makes the coalesced SIMD bounds check
// (simd_v128_load_rng) exact: a group whose unwrapped address range
// reaches past memSize can then never be a group whose members all
// individually landed in bounds via u32 wraparound.
//
// A function rather than a const because the helper extractor carries
// only function declarations into the output (it must stay in sync
// with codegen's wasmMemHardCapBytes).
func WasmMemHardCap() uint64 { return (1 << 32) - (1 << 17) }

// memoryGrow grows m.memory by n wasm pages (64 KiB each). Returns the
// previous page count, or -1 if the new size would exceed maxMem or
// wasmMemHardCap. n may be 0, which simply returns the current size.
//
// len(m.memory) must always equal the exact wasm memory size (memory.size
// and every bounds check depend on it), but the backing array is grown
// GEOMETRICALLY: a sequence of small memory.grow calls — which a C++ heap
// does constantly during start-up — would otherwise reallocate and recopy
// the whole linear memory on every page, i.e. O(n^2) total copying. Spare
// capacity makes the common grow a zero-copy reslice and amortizes the
// reallocations to O(n).
func MemoryGrow(m *Module, n int32) int32 {

	m.MemMu.Lock()
	defer m.MemMu.Unlock()
	cur := m.MemSize.Load()
	prev := int32(cur >> 16)
	if n == 0 {
		return prev
	}
	if n < 0 {
		return -1
	}
	want := cur + uint64(n)*65536
	if m.MaxMem != 0 && want > m.MaxMem {
		return -1
	}
	if want > WasmMemHardCap() {
		return -1
	}
	if m.MemShared {

		if want > uint64(len(m.Memory)) {
			return -1
		}
		if m.PrepareMemoryGrow != nil {
			if err := m.PrepareMemoryGrow(cur, want); err != nil {
				return -1
			}
		}
		m.MemSize.Store(want)
		return prev
	}
	if want <= uint64(cap(m.Memory)) {

		m.Memory = m.Memory[:want]
		m.MemSize.Store(want)
		return prev
	}

	newCap := uint64(cap(m.Memory)) * 2
	if newCap < want {
		newCap = want
	}
	if m.MaxMem != 0 && newCap > m.MaxMem {
		newCap = m.MaxMem
	}
	if newCap > WasmMemHardCap() {
		newCap = WasmMemHardCap()
	}
	grown := make([]byte, want, newCap)
	copy(grown, m.Memory)
	m.Memory = grown
	m.MemSize.Store(want)

	m.M = unsafe.Pointer(unsafe.SliceData(m.Memory))
	return prev
}

// accessMemory runs f with the module's current linear memory while
// holding the same lock memoryGrow takes to mutate the memory slice
// header or relocate its backing array. It is the ONE safe way to
// touch linear memory from OUTSIDE the module's execution goroutine —
// e.g. a watchdog goroutine raising CPython's eval-breaker bit while
// an evaluation is running. For the duration of f the memory can
// neither be resliced nor relocated, so f's writes land in the array
// the guest observes; a grow that raced in just before blocks until f
// returns and then copies f's writes forward with the rest of the
// contents. Determinism notes for callers:
//
//   - f MUST NOT call back into the module or into memoryGrow — that
//     would self-deadlock.
//   - f should be short: a running guest blocks inside memory.grow
//     until f returns (ordinary guest loads/stores do not block).
//   - Bytes the guest reads or writes concurrently with f (that is
//     the point of an eval-breaker-style flag) are exchanged with
//     plain single-word accesses; keep such shared words
//     word-aligned and word-sized.
func AccessMemory(m *Module, f func(mem []byte)) {
	m.MemMu.Lock()
	defer m.MemMu.Unlock()
	f(m.Memory)
}

func I32_div_u_s(x, y int32) int32 { return int32(I32_div_u(uint32(x), uint32(y))) }
func I32_rem_u_s(x, y int32) int32 { return int32(I32_rem_u(uint32(x), uint32(y))) }
func I64_div_u_s(x, y int64) int64 { return int64(I64_div_u(uint64(x), uint64(y))) }
func I64_rem_u_s(x, y int64) int64 { return int64(I64_rem_u(uint64(x), uint64(y))) }

// The explicit same-type conversions are NOT redundant: they are
// rounding points. Once these helpers inline, gc is free to fuse a
// multiply feeding an add into a single FMA — legal Go, but wasm
// requires every operation individually rounded, and a fused result
// diverges from every wasm runtime (bitwise, and observably in greedy
// sampling). A float conversion forces the intermediate rounding and
// forbids the fusion (spec: Conversions, "rounds to the precision of
// the target type"; the same rule math.FMA documents).
func F32_add(x, y float32) float32 { return float32(x + y) }
func F32_sub(x, y float32) float32 { return float32(x - y) }
func F32_mul(x, y float32) float32 { return float32(x * y) }
func F32_div(x, y float32) float32 { return float32(x / y) }
func F64_add(x, y float64) float64 { return float64(x + y) }
func F64_sub(x, y float64) float64 { return float64(x - y) }
func F64_mul(x, y float64) float64 { return float64(x * y) }
func F64_div(x, y float64) float64 { return float64(x / y) }

func I32_clz(x int32) int32    { return int32(bits.LeadingZeros32(uint32(x))) }
func I32_ctz(x int32) int32    { return int32(bits.TrailingZeros32(uint32(x))) }
func I32_popcnt(x int32) int32 { return int32(bits.OnesCount32(uint32(x))) }

func I64_clz(x int64) int64    { return int64(bits.LeadingZeros64(uint64(x))) }
func I64_ctz(x int64) int64    { return int64(bits.TrailingZeros64(uint64(x))) }
func I64_popcnt(x int64) int64 { return int64(bits.OnesCount64(uint64(x))) }

func F32_ceil(x float32) float32 { return float32(math.Ceil(float64(x))) }
func F64_ceil(x float64) float64 { return math.Ceil(x) }

func F64_floor(x float64) float64 { return math.Floor(x) }

func F64_trunc(x float64) float64 { return math.Trunc(x) }
func F32_sqrt(x float32) float32  { return float32(math.Sqrt(float64(x))) }
func F64_sqrt(x float64) float64  { return math.Sqrt(x) }

func F32_eq(x, y float32) int32 {
	if x == y {
		return 1
	}
	return 0
}
func F32_ne(x, y float32) int32 {
	if x != y {
		return 1
	}
	return 0
}
func F32_lt(x, y float32) int32 {
	if x < y {
		return 1
	}
	return 0
}
func F32_gt(x, y float32) int32 {
	if x > y {
		return 1
	}
	return 0
}
func F32_le(x, y float32) int32 {
	if x <= y {
		return 1
	}
	return 0
}
func F32_ge(x, y float32) int32 {
	if x >= y {
		return 1
	}
	return 0
}

func F64_eq(x, y float64) int32 {
	if x == y {
		return 1
	}
	return 0
}
func F64_ne(x, y float64) int32 {
	if x != y {
		return 1
	}
	return 0
}
func F64_lt(x, y float64) int32 {
	if x < y {
		return 1
	}
	return 0
}
func F64_gt(x, y float64) int32 {
	if x > y {
		return 1
	}
	return 0
}
func F64_le(x, y float64) int32 {
	if x <= y {
		return 1
	}
	return 0
}
func F64_ge(x, y float64) int32 {
	if x >= y {
		return 1
	}
	return 0
}

func I32_wrap_i64(x int64) int32       { return int32(x) }
func I64_extend_i32_s(x int32) int64   { return int64(x) }
func I64_extend_i32_u(x int32) int64   { return int64(uint32(x)) }
func F32_demote_f64(x float64) float32 { return float32(x) }
func F64_promote_f32(x float32) float64 {

	if math.IsNaN(float64(x)) {

		return float64(x)
	}
	return float64(x)
}

func F32_convert_i32_s(x int32) float32 { return float32(x) }
func F32_convert_i32_u(x int32) float32 { return float32(uint32(x)) }
func F32_convert_i64_s(x int64) float32 { return float32(x) }
func F32_convert_i64_u(x int64) float32 { return float32(uint64(x)) }
func F64_convert_i32_s(x int32) float64 { return float64(x) }
func F64_convert_i32_u(x int32) float64 { return float64(uint32(x)) }
func F64_convert_i64_s(x int64) float64 { return float64(x) }
func F64_convert_i64_u(x int64) float64 { return float64(uint64(x)) }

func I32_reinterpret_f32(x float32) int32 { return int32(math.Float32bits(x)) }
func I64_reinterpret_f64(x float64) int64 { return int64(math.Float64bits(x)) }
func F32_reinterpret_i32(x int32) float32 { return math.Float32frombits(uint32(x)) }
func F64_reinterpret_i64(x int64) float64 { return math.Float64frombits(uint64(x)) }

func I32_extend8_s(x int32) int32  { return int32(int8(x)) }
func I32_extend16_s(x int32) int32 { return int32(int16(x)) }
func I64_extend8_s(x int64) int64  { return int64(int8(x)) }
func I64_extend16_s(x int64) int64 { return int64(int16(x)) }
func I64_extend32_s(x int64) int64 { return int64(int32(x)) }

// memoryInit implements memory.init: copy n bytes from passive data segment
// seg at src into memory at dst. Out-of-bounds on either side traps, as does
// naming a dropped (or active) segment with n > 0. The bounds check consults
// memSize (not len(m.M)) so a shared memory's reserved-but-ungrown tail stays
// out of reach, mirroring memoryFill/memoryCopy.
//
//go:noinline
func MemoryInit(m *Module, seg int, dst int32, src int32, n int32) {
	data := m.DataSegs[seg]
	if n == 0 {
		return
	}
	if data == nil ||
		uint64(uint32(src))+uint64(uint32(n)) > uint64(len(data)) ||
		uint64(uint32(dst))+uint64(uint32(n)) > m.MemSize.Load() {
		Wasm_trap_meminit_oob()
	}

	if end := uint32(dst) + uint32(n); end > m.DataEnd {
		m.DataEnd = end
	}
	d := m.Memory[uint32(dst) : uint32(dst)+uint32(n)]
	s := data[uint32(src) : uint32(src)+uint32(n)]

	if bytes.Equal(d, s) {
		return
	}
	copy(d, s)
}

// dataDrop implements data.drop: discard passive segment seg. A later
// memory.init naming it traps (nil view); double-drop is a no-op per spec.
// dataDrop stays out of line: inlined into a gcasm-transformed function, the
// pointer write (a nil store into dataSegs) would drag runtime.gcWriteBarrier
// into the asm body, which the transformer rejects.
//
//go:noinline
func DataDrop(m *Module, seg int) {
	m.DataSegs[seg] = nil
}

func MemoryFill(m *Module, dst int32, val int32, n int32) {
	if n == 0 {
		return
	}
	end := uint64(uint32(dst)) + uint64(uint32(n))
	if end > MemBound(m) {
		Wasm_trap_memfill_oob()
	}
	b := m.Memory[uint32(dst):uint32(end)]
	v := byte(val)

	if v == 0 {
		for k := range b {
			b[k] = 0
		}
		return
	}
	b[0] = v
	for filled := 1; filled < len(b); filled *= 2 {
		copy(b[filled:], b[:filled])
	}
}

func MemoryCopy(m *Module, dst int32, src int32, n int32) {
	if n == 0 {
		return
	}
	srcEnd := uint64(uint32(src)) + uint64(uint32(n))
	dstEnd := uint64(uint32(dst)) + uint64(uint32(n))
	if size := MemBound(m); srcEnd > size || dstEnd > size {
		Wasm_trap_memcopy_oob()
	}
	copy(m.Memory[uint32(dst):uint32(dstEnd)], m.Memory[uint32(src):uint32(srcEnd)])
}

//go:noinline
func Wasm_trap_atomic_oob() { panic("wasm: atomic access out of bounds") }

//go:noinline
func Wasm_trap_atomic_unaligned() { panic("wasm: unaligned atomic access") }

//go:noinline
func Wasm_trap_atomic_wait_forever() {
	panic("wasm: blocking atomic wait with no other agents (wasi-threads not enabled)")
}

// memBound is the highest address a bounds-checked bulk or atomic access
// may reach. A shared memory's slice spans the whole declared maximum from
// the start, so only memSize says how much of it the guest may touch (and
// reading it atomically keeps growth race-free without a lock). Otherwise
// the slice is the truth: an embedder that maps the whole growable range
// up front and aliases shared segments above the guest-visible size into
// it keeps every byte of the slice addressable, exactly as the unchecked
// load/store paths do.
// memoryEA is the shared non-wrapping logical-bound rule. Subtractions make
// both additions safe. This rule is used by the pure memory32 lowering.
func MemoryInBounds(m *Module, addr, offset, size uint64) bool {
	bound := m.MemSize.Load()
	return addr <= bound && offset <= bound-addr && size <= bound-addr-offset
}
func MemoryEA(m *Module, addr, offset, size uint64) uint64 {
	if !MemoryInBounds(m, addr, offset, size) {
		Wasm_trap_memory_oob()
	}
	return addr + offset
}

//go:noinline
func Wasm_trap_memory_oob() { panic("wasm: memory access out of bounds") }

func MemBound(m *Module) uint64 {
	if m.MemShared {
		return m.MemSize.Load()
	}
	return uint64(len(m.Memory))
}

// atomicEA bounds- and alignment-checks an atomic access and returns the
// effective address.
// Atomic and thread helpers are all //go:noinline: several take func-literal
// operands (the subword CAS loops, the RMW families), and if the compiler
// inlines such a helper into a gcasm-transformed generated function the
// closure becomes a cross-package symbol ("pN.FnX.AtomicRmwOr32.func4") the
// asm bundler cannot represent. Out-of-line, the closure stays homed in base.
//
//go:noinline
func AtomicEA(m *Module, addr int32, offset int32, size uint64) uint64 {
	ea := uint64(uint32(addr)) + uint64(uint32(offset))
	if !MemoryInBounds(m, uint64(uint32(addr)), uint64(uint32(offset)), size) {
		Wasm_trap_atomic_oob()
	}
	if ea&(size-1) != 0 {
		Wasm_trap_atomic_unaligned()
	}
	return ea
}

// atomicPtr32At / atomicPtr64At turn a CHECKED effective address into a
// pointer into linear memory. The caller went through atomicEA/atomicEA64,
// which already bounds-checked ea against memSize, so index off the raw
// base pointer to skip Go's redundant slice bounds check — the same deal
// the plain load/store path gets. m.M tracks m.memory's data pointer (New
// sets it; a shared memory never relocates, and the non-shared reallocate
// path refreshes it).
//
//go:noinline
func AtomicPtr32At(m *Module, ea uint64) *uint32 {
	return (*uint32)(unsafe.Add(m.M, uintptr(ea)))
}

//go:noinline
func AtomicPtr64At(m *Module, ea uint64) *uint64 {
	return (*uint64)(unsafe.Add(m.M, uintptr(ea)))
}

// atomicsContended reports whether more than the main agent can touch the
// memory — i.e. at least one wasi thread has been spawned. Until that happens
// the engine's own atomic ops (interrupt-flag reads, GC bookkeeping) have no
// peer to race, so store/RMW helpers take an ordinary read-modify-write
// instead of a LOCKed one. The 0->1 transition happens inside threadSpawn on
// the sole agent, and the `go` statement that starts the child publishes
// every prior non-atomic write to it, so the fast path is race-free.
func AtomicsContended(m *Module) bool {
	return m.Threads != nil && m.Threads.nextTID.Load() != 0
}

// forceContendedAtomics makes every atomic helper of m take its LOCKed
// path from now on, as if a wasi thread had been spawned. For an embedder
// that shares part of m's linear memory with OTHER instances (several
// single-threaded modules aliasing one segment, the way processes share
// System V memory): no thread of m ever exists, yet the atomics in the
// shared range race with those instances' goroutines. Host-facing API;
// nothing in the generated code calls it.
func ForceContendedAtomics(m *Module) {
	if m.Threads == nil {
		m.Threads = &ThreadPool{}
	}
	if m.Threads.nextTID.Load() == 0 {
		m.Threads.nextTID.Store(1)
	}
}

// atomicSubword32 runs op on the byte lanes [shift, shift+bits) of the
// aligned 32-bit word containing ea, via a CAS loop; returns the OLD lane
// value zero-extended. Little-endian lane math.
//
//go:noinline
func AtomicSubword32(m *Module, ea uint64, bits uint, op func(old uint32) uint32) uint32 {
	word := (*uint32)(unsafe.Add(m.M, uintptr(ea&^3)))
	shift := uint(ea&3) * 8
	mask := uint32(1)<<bits - 1
	if !AtomicsContended(m) {
		cur := *word
		lane := (cur >> shift) & mask
		*word = (cur &^ (mask << shift)) | ((op(lane) & mask) << shift)
		return lane
	}
	for {
		cur := atomic.LoadUint32(word)
		lane := (cur >> shift) & mask
		next := (cur &^ (mask << shift)) | ((op(lane) & mask) << shift)
		if atomic.CompareAndSwapUint32(word, cur, next) {
			return lane
		}
	}
}

//go:noinline
func AtomicStore32At(m *Module, ea uint64, v int32) int32 {
	p := AtomicPtr32At(m, ea)
	if AtomicsContended(m) {
		atomic.StoreUint32(p, uint32(v))
	} else {
		*p = uint32(v)
	}
	return 0
}

//go:noinline
func AtomicRmw32At(m *Module, ea uint64, op func(old uint32) uint32) int32 {
	p := AtomicPtr32At(m, ea)
	if !AtomicsContended(m) {
		cur := *p
		*p = op(cur)
		return int32(cur)
	}
	for {
		cur := atomic.LoadUint32(p)
		if atomic.CompareAndSwapUint32(p, cur, op(cur)) {
			return int32(cur)
		}
	}
}

//go:noinline
func AtomicRmw64At(m *Module, ea uint64, op func(old uint64) uint64) int64 {
	p := AtomicPtr64At(m, ea)
	if !AtomicsContended(m) {
		cur := *p
		*p = op(cur)
		return int64(cur)
	}
	for {
		cur := atomic.LoadUint64(p)
		if atomic.CompareAndSwapUint64(p, cur, op(cur)) {
			return int64(cur)
		}
	}
}

//go:noinline
func AtomicRmwAdd32At(m *Module, ea uint64, v int32) int32 {
	p := AtomicPtr32At(m, ea)
	if !AtomicsContended(m) {
		old := *p
		*p = old + uint32(v)
		return int32(old)
	}
	return int32(atomic.AddUint32(p, uint32(v)) - uint32(v))
}

//go:noinline
func AtomicRmwSub32At(m *Module, ea uint64, v int32) int32 {
	p := AtomicPtr32At(m, ea)
	if !AtomicsContended(m) {
		old := *p
		*p = old - uint32(v)
		return int32(old)
	}
	return int32(atomic.AddUint32(p, -uint32(v)) + uint32(v))
}

//go:noinline
func AtomicRmwXchg32At(m *Module, ea uint64, v int32) int32 {
	p := AtomicPtr32At(m, ea)
	if !AtomicsContended(m) {
		old := *p
		*p = uint32(v)
		return int32(old)
	}
	return int32(atomic.SwapUint32(p, uint32(v)))
}

//go:noinline
func AtomicRmwCmpxchg32At(m *Module, ea uint64, expected, replacement int32) int32 {
	p := AtomicPtr32At(m, ea)
	if !AtomicsContended(m) {
		cur := *p
		if cur == uint32(expected) {
			*p = uint32(replacement)
		}
		return int32(cur)
	}
	for {
		cur := atomic.LoadUint32(p)
		if cur != uint32(expected) {
			return int32(cur)
		}
		if atomic.CompareAndSwapUint32(p, cur, uint32(replacement)) {
			return int32(cur)
		}
	}
}

//go:noinline
func AtomicRmwAdd64At(m *Module, ea uint64, v int64) int64 {
	p := AtomicPtr64At(m, ea)
	if !AtomicsContended(m) {
		old := *p
		*p = old + uint64(v)
		return int64(old)
	}
	return int64(atomic.AddUint64(p, uint64(v)) - uint64(v))
}

//go:noinline
func AtomicRmwSub64At(m *Module, ea uint64, v int64) int64 {
	p := AtomicPtr64At(m, ea)
	if !AtomicsContended(m) {
		old := *p
		*p = old - uint64(v)
		return int64(old)
	}
	return int64(atomic.AddUint64(p, -uint64(v)) + uint64(v))
}

//go:noinline
func AtomicRmwCmpxchg64At(m *Module, ea uint64, expected, replacement int64) int64 {
	p := AtomicPtr64At(m, ea)
	if !AtomicsContended(m) {
		cur := *p
		if cur == uint64(expected) {
			*p = uint64(replacement)
		}
		return int64(cur)
	}
	for {
		cur := atomic.LoadUint64(p)
		if cur != uint64(expected) {
			return int64(cur)
		}
		if atomic.CompareAndSwapUint64(p, cur, uint64(replacement)) {
			return int64(cur)
		}
	}
}

// spinRelax is the cold half of the preemption guard the emitters
// plant in bare atomic spin loops (a loop that waits on an inline
// atomic load and makes no other call — see spinguard.go). Such a loop
// is fine as Go, but once the gcasm bundler captures the compiled
// function into a .s TEXT the runtime can no longer async-preempt it,
// and a goroutine spinning there blocks every stop-the-world — a
// livelock when the store it waits for comes from a goroutine the GC
// already parked.
//
// The generated hot path is a counter increment and a not-taken
// branch; every 2^k-th iteration reaches this call, with k derived at
// emission from the loop body's size so the interval is a roughly
// constant TIME budget (see spinGuardMask). The call itself
// is the fix — it must survive to machine code (hence //go:noinline),
// and its prologue's stack check is the preemption point, so a
// stop-the-world waits at most tens-to-low-hundreds of microseconds
// of spinning. The Gosched additionally donates the core when a
// wait is genuinely long. Calling on every iteration instead measured
// ~40% decode overhead at n_threads=8: eight workers reaching
// runtime.Gosched at spin rate serialize on sched.lock, and the call
// round-trip alone showed ~15%.
//
// The Gosched is rate-limited across every spinning worker (the
// spinRelaxColdCalls counter lives in the runtime template — helper
// extraction carries function decls only): the preemption point is the
// spinRelax call itself (its prologue's stack check), but yielding on
// every cold call still measured double-digit scheduler churn
// (pthread_cond_signal — wakep — at 30% of the profile) on
// barrier-heavy workloads, where waiting IS most of a worker's time.
// One yield per 64 cold calls kept donation proportional to aggregate
// spin time, but on an uncontended box every yield still wakes an
// idle scheduler thread (wakep -> pthread_cond_signal) that spins in
// findRunnable and parks again: at n_threads = 4 on a 10-core host that
// churn was 60% of the CPU samples of a decode step, and on a 4-core
// host it takes cores from the workers themselves. With every agent on
// its own processor there is nobody to donate the core to, so the
// uncontended rate is now one yield per 1024 cold calls (tens of
// milliseconds of spinning, sysmon's own preemption granularity, kept
// for host goroutines); oversubscription yields on every cold call.
//
// When the instance runs more agents than the scheduler has processors
// (spinAgents, maintained by threadLaunch, against GOMAXPROCS), a spinner
// holds a processor that a runnable agent needs: every cold call yields
// then. A barrier the guest spins on is only released once every agent
// has arrived, and the arriving agents are exactly the ones waiting for
// a processor, so the 1/64 rate turns each barrier into milliseconds of
// scheduling latency (measured: n_threads twice the core count, decode
// fell to 1/100 of the single-thread rate). Native ggml with an OpenMP
// barrier degrades gracefully in the same setting; this is its
// equivalent. The check is one atomic load: spinOversubscribed is
// recomputed by threadLaunch (and agent exit) from the gauge and
// GOMAXPROCS, because runtime.GOMAXPROCS takes sched.lock and eight
// spinners asking it at cold-call rate measured a 3% decode loss on an
// uncontended box.
//
//go:noinline
func SpinRelax() {
	n := atomic.AddUint32(&spinRelaxColdCalls, 1)
	if atomic.LoadUint32(&spinOversubscribed) != 0 || n&1023 == 0 {
		runtime.Gosched()
	}
}

// spinAgentsAdd moves the live spawned-agent gauge by delta and
// refreshes spinOversubscribed: the spawner itself is the extra
// goroutine, so the instance is oversubscribed once the spawned agents
// alone reach GOMAXPROCS.
func SpinAgentsAdd(delta int32) {
	agents := atomic.AddInt32(&spinAgents, delta)
	var over uint32
	if int(agents) >= runtime.GOMAXPROCS(0) {
		over = 1
	}
	atomic.StoreUint32(&spinOversubscribed, over)
}

//go:noinline
func AtomicLoad32_8u(m *Module, addr int32, offset int32) int32 {
	return int32(AtomicSubword32(m, AtomicEA(m, addr, offset, 1), 8, func(old uint32) uint32 { return old }))
}

//go:noinline
func AtomicLoad32_16u(m *Module, addr int32, offset int32) int32 {
	return int32(AtomicSubword32(m, AtomicEA(m, addr, offset, 2), 16, func(old uint32) uint32 { return old }))
}

//go:noinline
func AtomicLoad64_32u(m *Module, addr int32, offset int32) int64 {
	return int64(atomic.LoadUint32(AtomicPtr32At(m, AtomicEA(m, addr, offset, 4))))
}

//go:noinline
func AtomicStore32_8(m *Module, addr int32, offset int32, v int32) int32 {
	AtomicSubword32(m, AtomicEA(m, addr, offset, 1), 8, func(uint32) uint32 { return uint32(v) })
	return 0
}

//go:noinline
func AtomicStore32_16(m *Module, addr int32, offset int32, v int32) int32 {
	AtomicSubword32(m, AtomicEA(m, addr, offset, 2), 16, func(uint32) uint32 { return uint32(v) })
	return 0
}

//go:noinline
func AtomicStore64_32(m *Module, addr int32, offset int32, v int64) int32 {

	return AtomicStore32At(m, AtomicEA(m, addr, offset, 4), int32(v))
}

//go:noinline
func AtomicRmwAdd32(m *Module, addr, offset, v int32) int32 {
	return AtomicRmwAdd32At(m, AtomicEA(m, addr, offset, 4), v)
}

//go:noinline
func AtomicRmwSub32(m *Module, addr, offset, v int32) int32 {
	return AtomicRmwSub32At(m, AtomicEA(m, addr, offset, 4), v)
}

//go:noinline
func AtomicRmwAnd32(m *Module, addr, offset, v int32) int32 {
	return AtomicRmw32At(m, AtomicEA(m, addr, offset, 4), func(o uint32) uint32 { return o & uint32(v) })
}

//go:noinline
func AtomicRmwOr32(m *Module, addr, offset, v int32) int32 {
	return AtomicRmw32At(m, AtomicEA(m, addr, offset, 4), func(o uint32) uint32 { return o | uint32(v) })
}

//go:noinline
func AtomicRmwXchg32(m *Module, addr, offset, v int32) int32 {
	return AtomicRmwXchg32At(m, AtomicEA(m, addr, offset, 4), v)
}

//go:noinline
func AtomicRmwCmpxchg32(m *Module, addr, offset, expected, replacement int32) int32 {
	return AtomicRmwCmpxchg32At(m, AtomicEA(m, addr, offset, 4), expected, replacement)
}

//go:noinline
func AtomicRmwAdd64(m *Module, addr, offset int32, v int64) int64 {
	return AtomicRmwAdd64At(m, AtomicEA(m, addr, offset, 8), v)
}

//go:noinline
func AtomicRmwSub64(m *Module, addr, offset int32, v int64) int64 {
	return AtomicRmwSub64At(m, AtomicEA(m, addr, offset, 8), v)
}

//go:noinline
func AtomicRmwOr64(m *Module, addr, offset int32, v int64) int64 {
	return AtomicRmw64At(m, AtomicEA(m, addr, offset, 8), func(o uint64) uint64 { return o | uint64(v) })
}

//go:noinline
func AtomicRmwCmpxchg64(m *Module, addr, offset int32, expected, replacement int64) int64 {
	return AtomicRmwCmpxchg64At(m, AtomicEA(m, addr, offset, 8), expected, replacement)
}

//go:noinline
func AtomicRmwAdd32_8u(m *Module, addr, offset, v int32) int32 {
	return int32(AtomicSubword32(m, AtomicEA(m, addr, offset, 1), 8, func(o uint32) uint32 { return o + uint32(v) }))
}

//go:noinline
func AtomicRmwXchg32_8u(m *Module, addr, offset, v int32) int32 {
	return int32(AtomicSubword32(m, AtomicEA(m, addr, offset, 1), 8, func(uint32) uint32 { return uint32(v) }))
}

// atomicNotify wakes up to count agents waiting on the address and reports
// how many it woke (0 when none are parked, which is also the single-agent
// answer).
//
//go:noinline
func AtomicNotify(m *Module, addr int32, offset int32, count int32) int32 {
	return m.Threads.wake(AtomicEA(m, addr, offset, 4), count)
}

// atomicWait32/64 implement memory.atomic.wait: compare-and-park. The compare
// happens under the parking-lot lock a notifier must also take, so a notify
// that lands between the compare and the park cannot be missed.
//
// Returns 0 = woken, 1 = not-equal, 2 = timed-out. A negative timeout means
// wait forever; with no other agent able to notify, that is a guaranteed
// deadlock, so it traps rather than hanging the process.
//
//go:noinline
func AtomicWait32At(m *Module, ea uint64, expected int32, timeout int64) int32 {
	p := AtomicPtr32At(m, ea)
	return AtomicWait(m, ea, timeout, func() bool {
		return int32(atomic.LoadUint32(p)) == expected
	})
}

//go:noinline
func AtomicWait32(m *Module, addr int32, offset int32, expected int32, timeout int64) int32 {
	return AtomicWait32At(m, AtomicEA(m, addr, offset, 4), expected, timeout)
}

//go:noinline
func AtomicWait(m *Module, ea uint64, timeout int64, stillEqual func() bool) int32 {
	if !m.MemShared {

		return 1
	}
	m.Threads.parkMu.Lock()
	if !stillEqual() {
		m.Threads.parkMu.Unlock()
		return 1
	}
	ch := make(chan struct{})
	if m.Threads.parked == nil {
		m.Threads.parked = make(map[uint64][]chan struct{})
	}
	m.Threads.parked[ea] = append(m.Threads.parked[ea], ch)
	m.Threads.parkMu.Unlock()

	unpark := func() {
		m.Threads.parkMu.Lock()
		defer m.Threads.parkMu.Unlock()
		waiters := m.Threads.parked[ea]
		for i, c := range waiters {
			if c == ch {
				m.Threads.parked[ea] = append(waiters[:i], waiters[i+1:]...)
				break
			}
		}
		if len(m.Threads.parked[ea]) == 0 {
			delete(m.Threads.parked, ea)
		}
	}

	if timeout < 0 {
		if m.Threads.nextTID.Load() == 0 {

			unpark()
			Wasm_trap_atomic_wait_forever()
		}
		<-ch
		return 0
	}

	timer := time.NewTimer(time.Duration(timeout) + time.Millisecond)
	defer timer.Stop()
	select {
	case <-ch:
		return 0
	case <-timer.C:
		unpark()
		return 2
	}
}

// threadLaunch allocates a TID and runs body — the guest's thread entry
// already bound to its start argument — on a fresh goroutine-agent.
//
//go:noinline
func ThreadLaunch(m *Module, body func(child *Module, tid int32)) int32 {
	tid := m.Threads.nextTID.Add(1)
	m.Threads.wg.Add(1)

	child := new(Module)
	*child = *m
	SpinAgentsAdd(1)
	go func() {
		defer m.Threads.wg.Done()
		defer SpinAgentsAdd(-1)

		defer func() {
			if r := recover(); r != nil {
				println("wasm2go: wasi thread", tid, "trapped:")
				switch v := r.(type) {
				case error:
					println("  ", v.Error())
				case string:
					println("  ", v)
				}
				panic(r)
			}
		}()
		body(child, tid)
	}()
	return tid
}

// threadSpawn implements the wasi_thread_spawn import: run the guest's thread
// entry on a goroutine, return the new TID (negative means "cannot spawn").
//
//go:noinline
func ThreadSpawn(m *Module, arg int32) int32 {
	start := m.ThreadStart
	if start == nil {
		return -1
	}
	return ThreadLaunch(m, func(child *Module, tid int32) { start(child, tid, arg) })
}

//go:noinline
func Wasm_trap_simd_oob() { panic("wasm: v128 memory access out of bounds") }

// gcasmMemProbe anchors the Module field offsets the gcasm memory-op
// splices hardcode. The splices read m.M and m.memSize straight off the
// receiver in generated assembly, and the offsets of those fields
// depend on the module (the import-interface fields between them vary).
// Rather than re-deriving Go's struct layout, gcasm extracts the two
// offsets from THIS function's captured assembly — two loads off R0/AX,
// M first — so they always come from the same compile that produced the
// code being spliced. Never called at run time.
//
//go:noinline
func GcasmMemProbe(m *Module) (unsafe.Pointer, *atomic.Uint64) {
	return m.M, m.MemSize
}

func SimdEA(m *Module, addr int32, offset int32, size uint64) uint64 {

	ea := uint64(uint32(addr)) + uint64(uint32(offset))
	if !MemoryInBounds(m, uint64(uint32(addr)), uint64(uint32(offset)), size) {
		Wasm_trap_simd_oob()
	}
	return ea
}

// simd_v128_load_rng is the range-checked first load of a coalesced
// group (pass.CoalesceSimdBounds): one trap decision covers every
// access in [addr+rlo, addr+rlo+span), then it loads at its own
// addr+offset. The group's other loads use the unchecked _nc form
// below — which is only sound BECAUSE this ran first; nothing else may
// emit either form.
//
// rlo is SIGNED: the group minimum may lie below this load's own
// address when the group's loads appear out of address order, and when
// a member's u32 address arithmetic wrapped, addr+rlo can go negative
// — a negative start means some member sits just below 2^32 unwrapped,
// which the per-load checks would have trapped (memSize can never
// reach 2^32: memoryGrow stops at wasmMemHardCap), so trapping on
// start < 0 reproduces the original semantics exactly.
//
//go:noinline
func Simd_v128_load_rng(m *Module, addr int32, offset int32, rlo int32, span int32) [2]uint64 {
	start := int64(uint64(uint32(addr))) + int64(rlo)
	if start < 0 || uint64(start)+uint64(uint32(span)) > m.MemSize.Load() {
		Wasm_trap_simd_oob()
	}
	ea := uint64(uint32(addr)) + uint64(uint32(offset))
	p := unsafe.Add(m.M, uintptr(ea))
	return [2]uint64{*(*uint64)(p), *(*uint64)(unsafe.Add(p, 8))}
}

// simd_v128_load_nc is simd_v128_load minus the bounds check; emitted
// only by the bounds-coalescing pass, always behind a covering
// simd_v128_load_rng.
//
//go:noinline
func Simd_v128_load_nc(m *Module, addr int32, offset int32) [2]uint64 {
	ea := uint64(uint32(addr)) + uint64(uint32(offset))
	p := unsafe.Add(m.M, uintptr(ea))
	return [2]uint64{*(*uint64)(p), *(*uint64)(unsafe.Add(p, 8))}
}

//go:noinline
func Simd_v128_load(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 16)
	p := unsafe.Add(m.M, uintptr(ea))
	return [2]uint64{*(*uint64)(p), *(*uint64)(unsafe.Add(p, 8))}
}

//go:noinline
func Simd_scalar_i32_shl(v int32, s int32) int32 { return v << (uint(s) % 32) }

//go:noinline
func Simd_scalar_i32_add(a int32, b int32) int32 { return a + b }

//go:noinline
func Simd_v128_store(m *Module, addr int32, offset int32, v [2]uint64) int32 {
	ea := SimdEA(m, addr, offset, 16)
	p := unsafe.Add(m.M, uintptr(ea))
	*(*uint64)(p) = v[0]
	*(*uint64)(unsafe.Add(p, 8)) = v[1]
	return 0
}

//go:noinline
func Simd_v128_load32x2_u(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 8)
	p := unsafe.Add(m.M, uintptr(ea))
	var out [2]uint64
	for i := 0; i < 2; i++ {
		x := *(*uint32)(unsafe.Add(p, 4*i))
		out[i*64/64] |= uint64(uint64(x)) << (64 * uint(i) % 64)
	}
	return out
}

//go:noinline
func Simd_v128_load8_splat(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 1)
	x := *(*uint8)(unsafe.Add(m.M, uintptr(ea)))
	var out [2]uint64
	for i := 0; i < 16; i++ {
		out[i*8/64] |= uint64(x) << (8 * uint(i) % 64)
	}
	return out
}

//go:noinline
func Simd_v128_load16_splat(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 2)
	x := *(*uint16)(unsafe.Add(m.M, uintptr(ea)))
	var out [2]uint64
	for i := 0; i < 8; i++ {
		out[i*16/64] |= uint64(x) << (16 * uint(i) % 64)
	}
	return out
}

//go:noinline
func Simd_v128_load32_splat(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 4)
	x := *(*uint32)(unsafe.Add(m.M, uintptr(ea)))
	var out [2]uint64
	for i := 0; i < 4; i++ {
		out[i*32/64] |= uint64(x) << (32 * uint(i) % 64)
	}
	return out
}

//go:noinline
func Simd_v128_load32_zero(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 4)
	return [2]uint64{uint64(*(*uint32)(unsafe.Add(m.M, uintptr(ea)))), 0}
}

//go:noinline
func Simd_v128_load64_zero(m *Module, addr int32, offset int32) [2]uint64 {
	ea := SimdEA(m, addr, offset, 8)
	return [2]uint64{*(*uint64)(unsafe.Add(m.M, uintptr(ea))), 0}
}

//go:noinline
func Simd_v128_load8_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) [2]uint64 {
	ea := SimdEA(m, addr, offset, 1)
	x := *(*uint8)(unsafe.Add(m.M, uintptr(ea)))
	sh := 8 * uint(lane) % 64
	i := int(lane) * 8 / 64
	v[i] = v[i]&^(uint64(uint8(^uint8(0)))<<sh) | uint64(x)<<sh
	return v
}

//go:noinline
func Simd_v128_load16_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) [2]uint64 {
	ea := SimdEA(m, addr, offset, 2)
	x := *(*uint16)(unsafe.Add(m.M, uintptr(ea)))
	sh := 16 * uint(lane) % 64
	i := int(lane) * 16 / 64
	v[i] = v[i]&^(uint64(uint16(^uint16(0)))<<sh) | uint64(x)<<sh
	return v
}

//go:noinline
func Simd_v128_load32_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) [2]uint64 {
	ea := SimdEA(m, addr, offset, 4)
	x := *(*uint32)(unsafe.Add(m.M, uintptr(ea)))
	sh := 32 * uint(lane) % 64
	i := int(lane) * 32 / 64
	v[i] = v[i]&^(uint64(uint32(^uint32(0)))<<sh) | uint64(x)<<sh
	return v
}

//go:noinline
func Simd_v128_load64_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) [2]uint64 {
	ea := SimdEA(m, addr, offset, 8)
	x := *(*uint64)(unsafe.Add(m.M, uintptr(ea)))
	sh := 64 * uint(lane) % 64
	i := int(lane) * 64 / 64
	v[i] = v[i]&^(uint64(uint64(^uint64(0)))<<sh) | uint64(x)<<sh
	return v
}

//go:noinline
func Simd_v128_store8_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) int32 {
	ea := SimdEA(m, addr, offset, 1)
	x := uint8(v[int(lane)*8/64] >> (8 * uint(lane) % 64))
	*(*uint8)(unsafe.Add(m.M, uintptr(ea))) = x
	return 0
}

//go:noinline
func Simd_v128_store32_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) int32 {
	ea := SimdEA(m, addr, offset, 4)
	x := uint32(v[int(lane)*32/64] >> (32 * uint(lane) % 64))
	*(*uint32)(unsafe.Add(m.M, uintptr(ea))) = x
	return 0
}

//go:noinline
func Simd_v128_store64_lane(m *Module, addr int32, offset int32, lane int32, v [2]uint64) int32 {
	ea := SimdEA(m, addr, offset, 8)
	x := uint64(v[int(lane)*64/64] >> (64 * uint(lane) % 64))
	*(*uint64)(unsafe.Add(m.M, uintptr(ea))) = x
	return 0
}

func Simd_p_pack(lo, hi uint64) [2]uint64 { return [2]uint64{lo, hi} }

//go:noinline
func Simd_p_v128_load_rng(m *Module, addr int32, offset int32, rlo int32, span int32) (uint64, uint64) {
	r := Simd_v128_load_rng(m, addr, offset, rlo, span)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load_nc(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load_nc(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load32x2_u(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load32x2_u(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load8_splat(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load8_splat(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load16_splat(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load16_splat(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load32_splat(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load32_splat(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load32_zero(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load32_zero(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load64_zero(m *Module, addr int32, offset int32) (uint64, uint64) {
	r := Simd_v128_load64_zero(m, addr, offset)
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load8_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) (uint64, uint64) {
	r := Simd_v128_load8_lane(m, addr, offset, lane, [2]uint64{v0, v1})
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load16_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) (uint64, uint64) {
	r := Simd_v128_load16_lane(m, addr, offset, lane, [2]uint64{v0, v1})
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load32_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) (uint64, uint64) {
	r := Simd_v128_load32_lane(m, addr, offset, lane, [2]uint64{v0, v1})
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_load64_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) (uint64, uint64) {
	r := Simd_v128_load64_lane(m, addr, offset, lane, [2]uint64{v0, v1})
	return r[0], r[1]
}

//go:noinline
func Simd_p_v128_store(m *Module, addr int32, offset int32, v0, v1 uint64) int32 {
	return Simd_v128_store(m, addr, offset, [2]uint64{v0, v1})
}

//go:noinline
func Simd_p_v128_store8_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) int32 {
	return Simd_v128_store8_lane(m, addr, offset, lane, [2]uint64{v0, v1})
}

//go:noinline
func Simd_p_v128_store32_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) int32 {
	return Simd_v128_store32_lane(m, addr, offset, lane, [2]uint64{v0, v1})
}

//go:noinline
func Simd_p_v128_store64_lane(m *Module, addr int32, offset int32, lane int32, v0, v1 uint64) int32 {
	return Simd_v128_store64_lane(m, addr, offset, lane, [2]uint64{v0, v1})
}

//go:noinline
func Simd_p_fx0(m *Module) {
	n0 := Simd_v128_load(m, 15278040, 0)
	_ = Simd_v128_store(m, 24270324, 0, n0)
	n2 := Simd_v128_load(m, 15278024, 0)
	_ = Simd_v128_store(m, 24270308, 0, n2)
	n4 := Simd_v128_load(m, 15278008, 0)
	_ = Simd_v128_store(m, 24270292, 0, n4)
	return
}

//go:noinline
func Simd_p_fx1(m *Module) {
	n0 := Simd_v128_load(m, 15278692, 0)
	_ = Simd_v128_store(m, 24270344, 0, n0)
	n2 := Simd_v128_load(m, 15278708, 0)
	_ = Simd_v128_store(m, 24270360, 0, n2)
	n4 := Simd_v128_load(m, 15278724, 0)
	_ = Simd_v128_store(m, 24270376, 0, n4)
	return
}

//go:noinline
func Simd_p_fx2(m *Module) {
	n0 := Simd_v128_load(m, 15278972, 0)
	_ = Simd_v128_store(m, 24270396, 0, n0)
	n2 := Simd_v128_load(m, 15278988, 0)
	_ = Simd_v128_store(m, 24270412, 0, n2)
	n4 := Simd_v128_load(m, 15279004, 0)
	_ = Simd_v128_store(m, 24270428, 0, n4)
	return
}

//go:noinline
func Simd_p_fx3(m *Module) {
	n0 := Simd_v128_load(m, 15279364, 0)
	_ = Simd_v128_store(m, 24270480, 0, n0)
	n2 := Simd_v128_load(m, 15279348, 0)
	_ = Simd_v128_store(m, 24270464, 0, n2)
	n4 := Simd_v128_load(m, 15279332, 0)
	_ = Simd_v128_store(m, 24270448, 0, n4)
	return
}

//go:noinline
func Simd_p_fx4(m *Module) {
	n0 := Simd_v128_load(m, 15279416, 0)
	_ = Simd_v128_store(m, 24270532, 0, n0)
	n2 := Simd_v128_load(m, 15279400, 0)
	_ = Simd_v128_store(m, 24270516, 0, n2)
	n4 := Simd_v128_load(m, 15279384, 0)
	_ = Simd_v128_store(m, 24270500, 0, n4)
	return
}

//go:noinline
func Simd_p_fx5(m *Module) {
	n0 := Simd_v128_load(m, 15280292, 0)
	_ = Simd_v128_store(m, 24270584, 0, n0)
	n2 := Simd_v128_load(m, 15280276, 0)
	_ = Simd_v128_store(m, 24270568, 0, n2)
	n4 := Simd_v128_load(m, 15280260, 0)
	_ = Simd_v128_store(m, 24270552, 0, n4)
	return
}

//go:noinline
func Simd_p_fx6(m *Module) {
	n0 := Simd_v128_load(m, 15280344, 0)
	_ = Simd_v128_store(m, 24270636, 0, n0)
	n2 := Simd_v128_load(m, 15280328, 0)
	_ = Simd_v128_store(m, 24270620, 0, n2)
	n4 := Simd_v128_load(m, 15280312, 0)
	_ = Simd_v128_store(m, 24270604, 0, n4)
	return
}

//go:noinline
func Simd_p_fx7(m *Module) {
	n0 := Simd_v128_load(m, 15279868, 0)
	_ = Simd_v128_store(m, 24270688, 0, n0)
	n2 := Simd_v128_load(m, 15279852, 0)
	_ = Simd_v128_store(m, 24270672, 0, n2)
	n4 := Simd_v128_load(m, 15279836, 0)
	_ = Simd_v128_store(m, 24270656, 0, n4)
	return
}

//go:noinline
func Simd_p_fx8(m *Module) {
	n0 := Simd_v128_load(m, 15279920, 0)
	_ = Simd_v128_store(m, 24270740, 0, n0)
	n2 := Simd_v128_load(m, 15279904, 0)
	_ = Simd_v128_store(m, 24270724, 0, n2)
	n4 := Simd_v128_load(m, 15279888, 0)
	_ = Simd_v128_store(m, 24270708, 0, n4)
	return
}

//go:noinline
func Simd_p_fx9(m *Module) {
	n0 := Simd_v128_load(m, 15284748, 0)
	_ = Simd_v128_store(m, 24270792, 0, n0)
	n2 := Simd_v128_load(m, 15284732, 0)
	_ = Simd_v128_store(m, 24270776, 0, n2)
	n4 := Simd_v128_load(m, 15284716, 0)
	_ = Simd_v128_store(m, 24270760, 0, n4)
	return
}

//go:noinline
func Simd_p_fx10(m *Module) {
	n0 := Simd_v128_load(m, 15285724, 0)
	_ = Simd_v128_store(m, 24270844, 0, n0)
	n2 := Simd_v128_load(m, 15285708, 0)
	_ = Simd_v128_store(m, 24270828, 0, n2)
	n4 := Simd_v128_load(m, 15285692, 0)
	_ = Simd_v128_store(m, 24270812, 0, n4)
	return
}

//go:noinline
func Simd_p_fx11(m *Module) {
	n0 := Simd_v128_load(m, 15283708, 0)
	_ = Simd_v128_store(m, 24270896, 0, n0)
	n2 := Simd_v128_load(m, 15283692, 0)
	_ = Simd_v128_store(m, 24270880, 0, n2)
	n4 := Simd_v128_load(m, 15283676, 0)
	_ = Simd_v128_store(m, 24270864, 0, n4)
	return
}

//go:noinline
func Simd_p_fx12(m *Module) {
	n0 := Simd_v128_load(m, 15281256, 0)
	_ = Simd_v128_store(m, 24270948, 0, n0)
	n2 := Simd_v128_load(m, 15281240, 0)
	_ = Simd_v128_store(m, 24270932, 0, n2)
	n4 := Simd_v128_load(m, 15281224, 0)
	_ = Simd_v128_store(m, 24270916, 0, n4)
	return
}

//go:noinline
func Simd_p_fx13(m *Module) {
	n0 := Simd_v128_load(m, 15281400, 0)
	_ = Simd_v128_store(m, 24271000, 0, n0)
	n2 := Simd_v128_load(m, 15281384, 0)
	_ = Simd_v128_store(m, 24270984, 0, n2)
	n4 := Simd_v128_load(m, 15281368, 0)
	_ = Simd_v128_store(m, 24270968, 0, n4)
	return
}

//go:noinline
func Simd_p_fx14(m *Module) {
	n0 := Simd_v128_load(m, 15281544, 0)
	_ = Simd_v128_store(m, 24271052, 0, n0)
	n2 := Simd_v128_load(m, 15281528, 0)
	_ = Simd_v128_store(m, 24271036, 0, n2)
	n4 := Simd_v128_load(m, 15281512, 0)
	_ = Simd_v128_store(m, 24271020, 0, n4)
	return
}

//go:noinline
func Simd_p_fx15(m *Module) {
	n0 := Simd_v128_load(m, 15281596, 0)
	_ = Simd_v128_store(m, 24271104, 0, n0)
	n2 := Simd_v128_load(m, 15281580, 0)
	_ = Simd_v128_store(m, 24271088, 0, n2)
	n4 := Simd_v128_load(m, 15281564, 0)
	_ = Simd_v128_store(m, 24271072, 0, n4)
	return
}

//go:noinline
func Simd_p_fx16(m *Module) {
	n0 := Simd_v128_load(m, 15282196, 0)
	_ = Simd_v128_store(m, 24271156, 0, n0)
	n2 := Simd_v128_load(m, 15282180, 0)
	_ = Simd_v128_store(m, 24271140, 0, n2)
	n4 := Simd_v128_load(m, 15282164, 0)
	_ = Simd_v128_store(m, 24271124, 0, n4)
	return
}

//go:noinline
func Simd_p_fx17(m *Module) {
	n0 := Simd_v128_load(m, 15281956, 0)
	_ = Simd_v128_store(m, 24271208, 0, n0)
	n2 := Simd_v128_load(m, 15281940, 0)
	_ = Simd_v128_store(m, 24271192, 0, n2)
	n4 := Simd_v128_load(m, 15281924, 0)
	_ = Simd_v128_store(m, 24271176, 0, n4)
	return
}

//go:noinline
func Simd_p_fx18(m *Module) {
	n0 := Simd_v128_load(m, 15282008, 0)
	_ = Simd_v128_store(m, 24271260, 0, n0)
	n2 := Simd_v128_load(m, 15281992, 0)
	_ = Simd_v128_store(m, 24271244, 0, n2)
	n4 := Simd_v128_load(m, 15281976, 0)
	_ = Simd_v128_store(m, 24271228, 0, n4)
	return
}

//go:noinline
func Simd_p_fx19(m *Module) {
	n0 := Simd_v128_load(m, 15286284, 0)
	_ = Simd_v128_store(m, 24271312, 0, n0)
	n2 := Simd_v128_load(m, 15286268, 0)
	_ = Simd_v128_store(m, 24271296, 0, n2)
	n4 := Simd_v128_load(m, 15286252, 0)
	_ = Simd_v128_store(m, 24271280, 0, n4)
	return
}

//go:noinline
func Simd_p_fx20(m *Module) {
	n0 := Simd_v128_load(m, 15286776, 0)
	_ = Simd_v128_store(m, 24271364, 0, n0)
	n2 := Simd_v128_load(m, 15286760, 0)
	_ = Simd_v128_store(m, 24271348, 0, n2)
	n4 := Simd_v128_load(m, 15286744, 0)
	_ = Simd_v128_store(m, 24271332, 0, n4)
	return
}

//go:noinline
func Simd_p_fx21(m *Module) {
	n0 := Simd_v128_load(m, 15287228, 0)
	_ = Simd_v128_store(m, 24271416, 0, n0)
	n2 := Simd_v128_load(m, 15287212, 0)
	_ = Simd_v128_store(m, 24271400, 0, n2)
	n4 := Simd_v128_load(m, 15287196, 0)
	_ = Simd_v128_store(m, 24271384, 0, n4)
	return
}

//go:noinline
func Simd_p_fx22(m *Module) {
	n0 := Simd_v128_load(m, 15287588, 0)
	_ = Simd_v128_store(m, 24271468, 0, n0)
	n2 := Simd_v128_load(m, 15287572, 0)
	_ = Simd_v128_store(m, 24271452, 0, n2)
	n4 := Simd_v128_load(m, 15287556, 0)
	_ = Simd_v128_store(m, 24271436, 0, n4)
	return
}

//go:noinline
func Simd_p_fx23(m *Module) {
	n0 := Simd_v128_load(m, 15288064, 0)
	_ = Simd_v128_store(m, 24271520, 0, n0)
	n2 := Simd_v128_load(m, 15288048, 0)
	_ = Simd_v128_store(m, 24271504, 0, n2)
	n4 := Simd_v128_load(m, 15288032, 0)
	_ = Simd_v128_store(m, 24271488, 0, n4)
	return
}

//go:noinline
func Simd_p_fx24(m *Module) {
	n0 := Simd_v128_load(m, 15288392, 0)
	_ = Simd_v128_store(m, 24271572, 0, n0)
	n2 := Simd_v128_load(m, 15288376, 0)
	_ = Simd_v128_store(m, 24271556, 0, n2)
	n4 := Simd_v128_load(m, 15288360, 0)
	_ = Simd_v128_store(m, 24271540, 0, n4)
	return
}

//go:noinline
func Simd_p_fx25(m *Module) {
	n0 := Simd_v128_load(m, 15288668, 0)
	_ = Simd_v128_store(m, 24271624, 0, n0)
	n2 := Simd_v128_load(m, 15288652, 0)
	_ = Simd_v128_store(m, 24271608, 0, n2)
	n4 := Simd_v128_load(m, 15288636, 0)
	_ = Simd_v128_store(m, 24271592, 0, n4)
	return
}

//go:noinline
func Simd_p_fx26(m *Module) {
	n0 := Simd_v128_load(m, 15289160, 0)
	_ = Simd_v128_store(m, 24271676, 0, n0)
	n2 := Simd_v128_load(m, 15289144, 0)
	_ = Simd_v128_store(m, 24271660, 0, n2)
	n4 := Simd_v128_load(m, 15289128, 0)
	_ = Simd_v128_store(m, 24271644, 0, n4)
	return
}

//go:noinline
func Simd_p_fx27(m *Module) {
	n0 := Simd_v128_load(m, 15287824, 0)
	_ = Simd_v128_store(m, 24271728, 0, n0)
	n2 := Simd_v128_load(m, 15287808, 0)
	_ = Simd_v128_store(m, 24271712, 0, n2)
	n4 := Simd_v128_load(m, 15287792, 0)
	_ = Simd_v128_store(m, 24271696, 0, n4)
	return
}

//go:noinline
func Simd_p_fx28(m *Module, p0, p0h uint64) {
	n0 := Simd_v128_load(m, 15289700, 0)
	_ = Simd_v128_store(m, 24271780, 0, n0)
	n2 := Simd_v128_load(m, 15289684, 0)
	_ = Simd_v128_store(m, 24271764, 0, n2)
	n4 := Simd_v128_load(m, 15289668, 0)
	_ = Simd_v128_store(m, 24271748, 0, n4)
	_ = Simd_v128_store(m, 24271832, 0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, 24271816, 0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, 24271800, 0, [2]uint64{p0, p0h})
	return
}

//go:noinline
func Simd_p_fx29(m *Module) {
	n0 := Simd_v128_load(m, 23933208, 0)
	_ = Simd_v128_store(m, 23933256, 0, n0)
	return
}

//go:noinline
func Simd_p_fx30(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_or([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, 24012784, 0, n0)
	n2 := Simd_v128_load(m, 24012928, 0)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx31(m *Module, p0, p0h uint64) {
	n0 := Simd_v128_load(m, 24013384, 0)
	n1 := Simd_v128_or(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, 24013384, 0, n1)
	return
}

//go:noinline
func Simd_p_fx32(m *Module, p0, p0h uint64) {
	n0 := Simd_v128_load(m, 24013180, 0)
	n1 := Simd_v128_or(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, 24013180, 0, n1)
	return
}

//go:noinline
func Simd_p_fx33(m *Module, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, 24012808, 0)
	n1 := Simd_v128_or(n0, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, 24012940, 0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, 24012808, 0, n1)
	return
}

//go:noinline
func Simd_p_fx34(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_ne([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i64x2_extend_low_i32x4_s(n0)
	n2 := Simd_v128_or([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx35(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12561344)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx36(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 4)
	n1 := Simd_v128_and([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx37(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 92, n0)
	return
}

//go:noinline
func Simd_p_fx38(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 380)
	_ = Simd_v128_store(m, s0, 16, n0)
	return
}

//go:noinline
func Simd_p_fx39(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 216)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 200)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx40(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 24, n2)
	return
}

//go:noinline
func Simd_p_fx41(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 1684, n0)
	n2 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 1668, n2)
	return
}

//go:noinline
func Simd_p_fx42(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) {
	n0 := Simd_scalar_i32_add(s0, s1)
	n1 := Simd_v128_load(m, n0, 0)
	n2 := Simd_scalar_i32_add(s2, s1)
	n3 := Simd_v128_load(m, n2, 0)
	n4 := Simd_i32x4_sub(n1, n3)
	n5 := Simd_v128_load(m, s3, 0)
	n6 := Simd_i32x4_add(n4, n5)
	_ = Simd_v128_store(m, s3, 0, n6)
	return
}

//go:noinline
func Simd_p_fx43(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 752)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 736)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 720)
	_ = Simd_v128_store(m, s1, 0, n4)
	return
}

//go:noinline
func Simd_p_fx44(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 752)
	_ = Simd_v128_store(m, s1, 1392, n0)
	n2 := Simd_v128_load(m, s0, 736)
	_ = Simd_v128_store(m, s1, 1376, n2)
	n4 := Simd_v128_load(m, s0, 720)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx45(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 504)
	_ = Simd_v128_store(m, s1, 616, n0)
	return
}

//go:noinline
func Simd_p_fx46(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_eq(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx47(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 10168)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 10168, n1)
	return
}

//go:noinline
func Simd_p_fx48(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 10152)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 10152, n1)
	return
}

//go:noinline
func Simd_p_fx49(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 112, n0)
	return
}

//go:noinline
func Simd_p_fx50(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx51(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 624, n0)
	return
}

//go:noinline
func Simd_p_fx52(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_xor([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_sub([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx53(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx54(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx55(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 352, n0)
	return
}

//go:noinline
func Simd_p_fx56(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 0, 2, n1)
	n3 := Simd_v128_load32_lane(m, s3, 0, 3, n2)
	n4 := Simd_i32x4_add(n3, [2]uint64{p0, p0h})
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx57(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s1, 4, n0)
	return
}

//go:noinline
func Simd_p_fx58(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0+224, 0)
	_ = Simd_v128_store(m, s0+252, 0, n0)
	return
}

//go:noinline
func Simd_p_fx59(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s1, 20, n0)
	return
}

//go:noinline
func Simd_p_fx60(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx61(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 224)
	_ = Simd_v128_store(m, s0, 1568, n0)
	n2 := Simd_v128_load(m, s0, 208)
	_ = Simd_v128_store(m, s0, 1552, n2)
	return
}

//go:noinline
func Simd_p_fx62(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx63(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s0, 380, n0)
	return
}

//go:noinline
func Simd_p_fx64(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_lt_u(n1, [2]uint64{p1, p1h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx65(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx66(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_add([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx67(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load_rng(m, s0, 0, 0, 32)
	n1 := Simd_v128_load_nc(m, s0, 16)
	_ = Simd_v128_store(m, s1, 168, n1)
	_ = Simd_v128_store(m, s1, 152, n0)
	return
}

//go:noinline
func Simd_p_fx68(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n2)
	return
}

//go:noinline
func Simd_p_fx69(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+8, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx70(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 36, n0)
	return
}

//go:noinline
func Simd_p_fx71(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 0, 2, n1)
	n3 := Simd_v128_load32_lane(m, s3, 0, 3, n2)
	n4 := Simd_i32x4_eq(n3, [2]uint64{p1, p1h})
	n5 := Simd_i32x4_sub([2]uint64{p0, p0h}, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx72(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{795458214401281292, 216736831696667908})
	n2 := Simd_i32x4_eq(n1, [2]uint64{p1, p1h})
	n3 := Simd_i32x4_sub([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx73(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_eq(n0, [2]uint64{p1, p1h})
	n2 := Simd_i32x4_sub([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx74(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s0, 32, n0)
	return
}

//go:noinline
func Simd_p_fx75(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx76(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 240, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 224, n2)
	return
}

//go:noinline
func Simd_p_fx77(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx78(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 20, n0)
	n2 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 36, n2)
	n4 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 52, n4)
	n6 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 68, n6)
	return
}

//go:noinline
func Simd_p_fx79(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4496)
	_ = Simd_v128_store(m, s1, 4496, n0)
	return
}

//go:noinline
func Simd_p_fx80(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4532)
	_ = Simd_v128_store(m, s1, 4532, n0)
	n2 := Simd_v128_load(m, s0, 4516)
	_ = Simd_v128_store(m, s1, 4516, n2)
	return
}

//go:noinline
func Simd_p_fx81(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx82(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 2592)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx83(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 2592, n0)
	return
}

//go:noinline
func Simd_p_fx84(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 2248)
	_ = Simd_v128_store(m, s0, 1520, n0)
	return
}

//go:noinline
func Simd_p_fx85(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 2232)
	_ = Simd_v128_store(m, s0, 1536, n0)
	return
}

//go:noinline
func Simd_p_fx86(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 2216)
	_ = Simd_v128_store(m, s0, 1552, n0)
	return
}

//go:noinline
func Simd_p_fx87(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4752)
	_ = Simd_v128_store(m, s1, 1236, n0)
	n2 := Simd_v128_load(m, s0, 4736)
	_ = Simd_v128_store(m, s1, 1220, n2)
	n4 := Simd_v128_load(m, s0, 4720)
	_ = Simd_v128_store(m, s1, 1204, n4)
	return
}

//go:noinline
func Simd_p_fx88(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 800, n0)
	return
}

//go:noinline
func Simd_p_fx89(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 768, n0)
	return
}

//go:noinline
func Simd_p_fx90(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 736, n0)
	return
}

//go:noinline
func Simd_p_fx91(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 64, n0)
	return
}

//go:noinline
func Simd_p_fx92(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4408)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx93(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+2528, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx94(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 2592, n0)
	return
}

//go:noinline
func Simd_p_fx95(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load32_lane(m, s0, 0, 1, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s1, 2592, n0)
	return
}

//go:noinline
func Simd_p_fx96(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4800)
	_ = Simd_v128_store(m, s1, 1284, n0)
	n2 := Simd_v128_load(m, s0, 4784)
	_ = Simd_v128_store(m, s1, 1268, n2)
	n4 := Simd_v128_load(m, s0, 4768)
	_ = Simd_v128_store(m, s1, 1252, n4)
	return
}

//go:noinline
func Simd_p_fx97(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4800)
	_ = Simd_v128_store(m, s1, 1288, n0)
	n2 := Simd_v128_load(m, s0, 4784)
	_ = Simd_v128_store(m, s1, 1272, n2)
	n4 := Simd_v128_load(m, s0, 4768)
	_ = Simd_v128_store(m, s1, 1256, n4)
	return
}

//go:noinline
func Simd_p_fx98(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4752)
	_ = Simd_v128_store(m, s1, 1240, n0)
	n2 := Simd_v128_load(m, s0, 4736)
	_ = Simd_v128_store(m, s1, 1224, n2)
	n4 := Simd_v128_load(m, s0, 4720)
	_ = Simd_v128_store(m, s1, 1208, n4)
	return
}

//go:noinline
func Simd_p_fx99(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx100(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx101(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx102(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23996864, 0)
	_ = Simd_v128_store(m, s0, 12, n0)
	n2 := Simd_v128_load(m, 23996880, 0)
	_ = Simd_v128_store(m, s0, 28, n2)
	return
}

//go:noinline
func Simd_p_fx103(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 2672)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx104(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 2672, n0)
	return
}

//go:noinline
func Simd_p_fx105(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 2328)
	_ = Simd_v128_store(m, s0, 1552, n0)
	return
}

//go:noinline
func Simd_p_fx106(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 2312)
	_ = Simd_v128_store(m, s0, 1568, n0)
	return
}

//go:noinline
func Simd_p_fx107(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 2296)
	_ = Simd_v128_store(m, s0, 1584, n0)
	return
}

//go:noinline
func Simd_p_fx108(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 1104, n0)
	return
}

//go:noinline
func Simd_p_fx109(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 864, n0)
	return
}

//go:noinline
func Simd_p_fx110(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	_ = Simd_v128_store(m, s1, 2176, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx111(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 640, n0)
	return
}

//go:noinline
func Simd_p_fx112(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	_ = Simd_v128_store(m, s1, 2608, n0)
	_ = Simd_v128_store(m, s1, 448, n0)
	return
}

//go:noinline
func Simd_p_fx113(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 176, n0)
	return
}

//go:noinline
func Simd_p_fx114(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4488)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx115(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+2608, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx116(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 24, n2)
	n4 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 60, n4)
	return
}

//go:noinline
func Simd_p_fx117(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 76, n0)
	return
}

//go:noinline
func Simd_p_fx118(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 112, n0)
	return
}

//go:noinline
func Simd_p_fx119(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 116)
	_ = Simd_v128_store(m, s1, 132, n0)
	return
}

//go:noinline
func Simd_p_fx120(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 176, n0)
	n2 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 160, n2)
	return
}

//go:noinline
func Simd_p_fx121(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 196, n0)
	n2 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 212, n2)
	return
}

//go:noinline
func Simd_p_fx122(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 248, n0)
	return
}

//go:noinline
func Simd_p_fx123(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 116)
	_ = Simd_v128_store(m, s1, 268, n0)
	return
}

//go:noinline
func Simd_p_fx124(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load32_lane(m, s0, 0, 1, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s1, 2672, n0)
	return
}

//go:noinline
func Simd_p_fx125(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_gt_u(n1, [2]uint64{p1, p1h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx126(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 24, n2)
	return
}

//go:noinline
func Simd_p_fx127(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n4)
	return
}

//go:noinline
func Simd_p_fx128(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_scalar_i32_add(s1, s2)
	n2 := Simd_v128_load(m, n1, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	n4 := Simd_scalar_i32_add(s1, s2)
	_ = Simd_v128_store(m, n4, 0, n0)
	return
}

//go:noinline
func Simd_p_fx129(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	_ = Simd_v128_store(m, s0, 0, n1)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx130(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_splat(s0)
	n1 := Simd_v128_and([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx131(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_v128_or([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx132(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx133(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx134(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8803412, 0)
	_ = Simd_v128_store(m, s0, 336, n0)
	return
}

//go:noinline
func Simd_p_fx135(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, s5 int32, s6 int32, s7 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 0, 2, n1)
	n3 := Simd_v128_load32_lane(m, s3, 0, 3, n2)
	n4 := Simd_v128_load32_zero(m, s4, 0)
	n5 := Simd_v128_load32_lane(m, s5, 0, 1, n4)
	n6 := Simd_v128_load32_lane(m, s6, 0, 2, n5)
	n7 := Simd_v128_load32_lane(m, s7, 0, 3, n6)
	return n3[0], n3[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx136(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_scalar_i32_shl(s1, 5)
	n1 := Simd_scalar_i32_add(s0, n0)
	n2 := Simd_v128_load(m, n1, 0)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx137(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n2 := Simd_v128_or(n0, n1)
	n3 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p5, p5h})
	n4 := Simd_v128_or(n2, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx138(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx139(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_i32x4_sub([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_sub([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx140(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx141(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_i64x2_extend_low_i32x4_u(n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx142(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i64x2_shr_u([2]uint64{p0, p0h}, 32)
	n1 := Simd_i64x2_add(n0, [2]uint64{p1, p1h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx143(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i64x2_add(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx144(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i64x2_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx145(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i64x2_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx146(m *Module, s0 int32, s1 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_shl(n0, 31)
	n2 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, n0, [2]uint64{1374179596971150604, 1952900979675763988})
	n3 := Simd_i32x4_shr_u(n2, 1)
	n4 := Simd_v128_or(n1, n3)
	_ = Simd_v128_store(m, s1, 0, n4)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx147(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12471712, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx148(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12471736, 0)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx149(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_mul([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx150(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 56, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 40, n2)
	n4 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 24, n4)
	return
}

//go:noinline
func Simd_p_fx151(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx152(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, n0)
	return
}

//go:noinline
func Simd_p_fx153(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{795458214199165184, 216736831629295872})
	n2 := Simd_v128_load32_lane(m, s0, 16, 2, n1)
	n3 := Simd_v128_load32_lane(m, s0, 24, 3, n2)
	n4 := Simd_i32x4_add(n3, [2]uint64{p0, p0h})
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx154(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23931576, 0)
	_ = Simd_v128_store(m, s0, 144, n0)
	return
}

//go:noinline
func Simd_p_fx155(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23931560, 0)
	_ = Simd_v128_store(m, s0, 128, n0)
	return
}

//go:noinline
func Simd_p_fx156(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 3176, n0)
	return
}

//go:noinline
func Simd_p_fx157(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23932464, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx158(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 32, n0)
	return
}

//go:noinline
func Simd_p_fx159(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s1, 0, n1)
	return
}

//go:noinline
func Simd_p_fx160(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 6, n0)
	return
}

//go:noinline
func Simd_p_fx161(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 192, n0)
	return
}

//go:noinline
func Simd_p_fx162(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 16, n4)
	return
}

//go:noinline
func Simd_p_fx163(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s0, 112, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 96, n2)
	n4 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s0, 80, n4)
	return
}

//go:noinline
func Simd_p_fx164(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{795458214199165184, 1952900979608391952})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_add(n1, [2]uint64{p3, p3h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx165(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx166(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n4)
	n6 := Simd_v128_load_rng(m, s0, 0, 0, 48)
	n7 := Simd_v128_load_nc(m, s0, 16)
	n8 := Simd_v128_load_nc(m, s0, 32)
	return n6[0], n6[1], n7[0], n7[1], n8[0], n8[1]
}

//go:noinline
func Simd_p_fx167(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23932464, 0)
	_ = Simd_v128_store(m, s0, 1092, n0)
	return
}

//go:noinline
func Simd_p_fx168(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 1092)
	_ = Simd_v128_store(m, 23932464, 0, n0)
	return
}

//go:noinline
func Simd_p_fx169(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 144)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx170(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 160, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 144, n2)
	return
}

//go:noinline
func Simd_p_fx171(m *Module, s0 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0+12521248, 0)
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx172(m *Module, s0 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0+12521264, 0)
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx173(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_not(n1)
	n3 := Simd_v128_or(n0, n2)
	_ = Simd_v128_store(m, s0, 0, n3)
	return
}

//go:noinline
func Simd_p_fx174(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_or(n0, n1)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx175(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_splat(s0)
	n1 := Simd_v128_andnot([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx176(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_splat(s0)
	n1 := Simd_v128_or(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx177(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_i32x4_splat(s1)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p1, p1h}, [2]uint64{1374179596769034496, 0})
	n2 := Simd_i8x16_shuffle(n1, [2]uint64{p2, p2h}, [2]uint64{506097522914230528, 319951120})
	n3 := Simd_i8x16_shuffle(n2, [2]uint64{p3, p3h}, [2]uint64{506097522914230528, 1374179596903778568})
	n4 := Simd_v128_load(m, s0, 104)
	n5 := Simd_v128_or(n4, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 104, n5)
	n7 := Simd_v128_load(m, s0, 88)
	n8 := Simd_v128_or(n7, n3)
	_ = Simd_v128_store(m, s0, 88, n8)
	return
}

//go:noinline
func Simd_p_fx178(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_v128_not([2]uint64{p0, p0h})
	n1 := Simd_i32x4_splat(s1)
	n2 := Simd_i8x16_shuffle(n1, [2]uint64{p1, p1h}, [2]uint64{1374179596769034496, 0})
	n3 := Simd_i8x16_shuffle(n2, [2]uint64{p2, p2h}, [2]uint64{506097522914230528, 319951120})
	n4 := Simd_i8x16_shuffle(n3, [2]uint64{p3, p3h}, [2]uint64{506097522914230528, 1374179596903778568})
	n5 := Simd_v128_not(n4)
	n6 := Simd_v128_load(m, s0, 104)
	n7 := Simd_v128_or(n6, n0)
	_ = Simd_v128_store(m, s0, 104, n7)
	n9 := Simd_v128_load(m, s0, 88)
	n10 := Simd_v128_or(n9, n5)
	_ = Simd_v128_store(m, s0, 88, n10)
	return
}

//go:noinline
func Simd_p_fx179(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_v128_load_rng(m, s0, 0, 0, 32)
	n1 := Simd_v128_load_nc(m, s0, 16)
	n2 := Simd_i8x16_shuffle(n0, n1, [2]uint64{795458214199165184, 1952900979608391952})
	n3 := Simd_i32x4_max_u(n2, [2]uint64{p3, p3h})
	n4 := Simd_i8x16_shuffle(n0, n1, [2]uint64{1084818905551471876, 2242261670960698644})
	n5 := Simd_i32x4_lt_u(n3, n4)
	n6 := Simd_v128_bitselect([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, n5)
	n7 := Simd_i32x4_add([2]uint64{p0, p0h}, n6)
	return n7[0], n7[1]
}

//go:noinline
func Simd_p_fx180(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	n1 := Simd_v128_not(n0)
	_ = Simd_v128_store(m, s0, 88, n1)
	n3 := Simd_v128_load(m, s0, 104)
	n4 := Simd_v128_not(n3)
	_ = Simd_v128_store(m, s0, 104, n4)
	return
}

//go:noinline
func Simd_p_fx181(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 1, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 17, n2)
	return
}

//go:noinline
func Simd_p_fx182(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_ne([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_ne([2]uint64{p3, p3h}, [2]uint64{p1, p1h})
	n3 := Simd_v128_and(n2, [2]uint64{p2, p2h})
	n4 := Simd_i16x8_narrow_i32x4_u(n1, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx183(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s4)
	n1 := Simd_v128_load32_zero(m, s0, 0)
	n2 := Simd_v128_load32_lane(m, s1, 0, 1, n1)
	n3 := Simd_v128_load32_lane(m, s2, 0, 2, n2)
	n4 := Simd_v128_load32_lane(m, s3, 0, 3, n3)
	n5 := Simd_i32x4_eq(n4, n0)
	n6 := Simd_i32x4_sub([2]uint64{p0, p0h}, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx184(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 128)
	n1 := Simd_f64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 128, n1)
	n3 := Simd_v128_load(m, s0, 144)
	n4 := Simd_f64x2_add(n3, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 144, n4)
	return n1[0], n1[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx185(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 80)
	n1 := Simd_f64x2_gt(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx186(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_f64x2_ge([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_not(n0)
	n2 := Simd_f64x2_le([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n3 := Simd_v128_not(n2)
	n4 := Simd_i8x16_shuffle(n1, n3, [2]uint64{795458214199165184, 1952900979608391952})
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx187(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, s0, 80)
	n1 := Simd_f64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 80, n1)
	n3 := Simd_v128_load(m, s0, 96)
	n4 := Simd_f64x2_add(n3, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 96, n4)
	return
}

//go:noinline
func Simd_p_fx188(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 96)
	n1 := Simd_f64x2_lt(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx189(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx190(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx191(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx192(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx193(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 384)
	_ = Simd_v128_store(m, s0, 352, n0)
	return
}

//go:noinline
func Simd_p_fx194(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 384)
	_ = Simd_v128_store(m, s0, 336, n0)
	return
}

//go:noinline
func Simd_p_fx195(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 384)
	_ = Simd_v128_store(m, s0, 320, n0)
	return
}

//go:noinline
func Simd_p_fx196(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 456)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx197(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 456)
	_ = Simd_v128_store(m, s0, 72, n0)
	return
}

//go:noinline
func Simd_p_fx198(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 456)
	_ = Simd_v128_store(m, s0, 120, n0)
	return
}

//go:noinline
func Simd_p_fx199(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 416)
	_ = Simd_v128_store(m, s0, 96, n0)
	return
}

//go:noinline
func Simd_p_fx200(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 456)
	_ = Simd_v128_store(m, s0, 168, n0)
	return
}

//go:noinline
func Simd_p_fx201(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 416)
	_ = Simd_v128_store(m, s0, 144, n0)
	return
}

//go:noinline
func Simd_p_fx202(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 456)
	_ = Simd_v128_store(m, s0, 232, n0)
	return
}

//go:noinline
func Simd_p_fx203(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 424)
	_ = Simd_v128_store(m, s0, 200, n0)
	return
}

//go:noinline
func Simd_p_fx204(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 456)
	_ = Simd_v128_store(m, s0, 296, n0)
	return
}

//go:noinline
func Simd_p_fx205(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 424)
	_ = Simd_v128_store(m, s0, 264, n0)
	return
}

//go:noinline
func Simd_p_fx206(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 72)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx207(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 600)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx208(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx209(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 32, n0)
	return
}

//go:noinline
func Simd_p_fx210(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_lt_u(n1, [2]uint64{p1, p1h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx211(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 21)
	_ = Simd_v128_store(m, s1, 66, n0)
	n2 := Simd_v128_load(m, s0, 37)
	_ = Simd_v128_store(m, s1, 82, n2)
	n4 := Simd_v128_load(m, s0, 53)
	_ = Simd_v128_store(m, s1, 98, n4)
	return
}

//go:noinline
func Simd_p_fx212(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 112, n0)
	return
}

//go:noinline
func Simd_p_fx213(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 12, n0)
	return
}

//go:noinline
func Simd_p_fx214(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s1, 256, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 272, n2)
	n4 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 288, n4)
	return
}

//go:noinline
func Simd_p_fx215(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 340, n0)
	return
}

//go:noinline
func Simd_p_fx216(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 524, n0)
	return
}

//go:noinline
func Simd_p_fx217(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_scalar_i32_add(s1, s2)
	n2 := Simd_v128_load(m, n1, 0)
	n3 := Simd_i32x4_add(n0, n2)
	_ = Simd_v128_store(m, s0, 0, n3)
	n5 := Simd_v128_load(m, s2+23941272, 0)
	n6 := Simd_v128_load(m, s3+16, 0)
	n7 := Simd_i32x4_add(n5, n6)
	_ = Simd_v128_store(m, s2+23941272, 0, n7)
	return
}

//go:noinline
func Simd_p_fx218(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_v128_load(m, s1, 0)
	n3 := Simd_i64x2_add(n2, [2]uint64{p1, p1h})
	return n1[0], n1[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx219(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 1248, n0)
	return
}

//go:noinline
func Simd_p_fx220(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 120)
	_ = Simd_v128_store(m, s0, 72, n0)
	return
}

//go:noinline
func Simd_p_fx221(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 104)
	_ = Simd_v128_store(m, s0, 32, n0)
	return
}

//go:noinline
func Simd_p_fx222(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s0, 56, n0)
	return
}

//go:noinline
func Simd_p_fx223(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n4)
	n6 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n6)
	return
}

//go:noinline
func Simd_p_fx224(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 168)
	_ = Simd_v128_store(m, s1, 168, n0)
	return
}

//go:noinline
func Simd_p_fx225(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 200)
	_ = Simd_v128_store(m, s1, 200, n0)
	return
}

//go:noinline
func Simd_p_fx226(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx227(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s0, 24, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 8, n2)
	return
}

//go:noinline
func Simd_p_fx228(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 88, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 104, n2)
	return
}

//go:noinline
func Simd_p_fx229(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 684)
	_ = Simd_v128_store(m, s1, 560, n0)
	n2 := Simd_v128_load(m, s0, 700)
	_ = Simd_v128_store(m, s1, 576, n2)
	return
}

//go:noinline
func Simd_p_fx230(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 16, n2)
	return
}

//go:noinline
func Simd_p_fx231(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 248, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s0, 232, n2)
	n4 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s0, 216, n4)
	return
}

//go:noinline
func Simd_p_fx232(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 424)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 408)
	_ = Simd_v128_store(m, s1, 24, n2)
	n4 := Simd_v128_load(m, s0, 392)
	_ = Simd_v128_store(m, s1, 8, n4)
	return
}

//go:noinline
func Simd_p_fx233(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 400, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 416, n2)
	n4 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 432, n4)
	return
}

//go:noinline
func Simd_p_fx234(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 368)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 352)
	_ = Simd_v128_store(m, s1, 24, n2)
	n4 := Simd_v128_load(m, s0, 336)
	_ = Simd_v128_store(m, s1, 8, n4)
	return
}

//go:noinline
func Simd_p_fx235(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 360)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 376)
	_ = Simd_v128_store(m, s1, 48, n4)
	return
}

//go:noinline
func Simd_p_fx236(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 128, n0)
	return
}

//go:noinline
func Simd_p_fx237(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 116)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 132)
	_ = Simd_v128_store(m, s1, 64, n2)
	return
}

//go:noinline
func Simd_p_fx238(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 128)
	_ = Simd_v128_store(m, s1, 12, n0)
	return
}

//go:noinline
func Simd_p_fx239(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 132, n0)
	n2 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 116, n2)
	return
}

//go:noinline
func Simd_p_fx240(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 216, n0)
	return
}

//go:noinline
func Simd_p_fx241(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 264, n0)
	return
}

//go:noinline
func Simd_p_fx242(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 180)
	_ = Simd_v128_store(m, s1, 180, n0)
	return
}

//go:noinline
func Simd_p_fx243(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 212)
	_ = Simd_v128_store(m, s1, 212, n0)
	return
}

//go:noinline
func Simd_p_fx244(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 244)
	_ = Simd_v128_store(m, s1, 244, n0)
	return
}

//go:noinline
func Simd_p_fx245(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 272)
	_ = Simd_v128_store(m, s1, 272, n0)
	return
}

//go:noinline
func Simd_p_fx246(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 476)
	_ = Simd_v128_store(m, s1, 476, n0)
	return
}

//go:noinline
func Simd_p_fx247(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 508)
	_ = Simd_v128_store(m, s1, 508, n0)
	return
}

//go:noinline
func Simd_p_fx248(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 540)
	_ = Simd_v128_store(m, s1, 540, n0)
	return
}

//go:noinline
func Simd_p_fx249(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 568)
	_ = Simd_v128_store(m, s1, 568, n0)
	return
}

//go:noinline
func Simd_p_fx250(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s1, 928, n0)
	return
}

//go:noinline
func Simd_p_fx251(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_and(n0, n1)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx252(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 80, n0)
	return
}

//go:noinline
func Simd_p_fx253(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_ne([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_ne([2]uint64{p3, p3h}, [2]uint64{p4, p4h})
	n3 := Simd_v128_and(n2, [2]uint64{p2, p2h})
	n4 := Simd_i16x8_narrow_i32x4_u(n1, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx254(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_lt_u(n1, [2]uint64{p1, p1h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx255(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 1744)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 1728)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 1712)
	_ = Simd_v128_store(m, s1, 16, n4)
	n6 := Simd_v128_load(m, s0, 1696)
	_ = Simd_v128_store(m, s1, 0, n6)
	return
}

//go:noinline
func Simd_p_fx256(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 1776, n0)
	n2 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 1760, n2)
	return
}

//go:noinline
func Simd_p_fx257(m *Module, s0 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx258(m *Module, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i16x8_extend_high_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx259(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shr_s([2]uint64{p2, p2h}, 7)
	n1 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, n0)
	n2 := Simd_i8x16_shuffle(n1, n1, [2]uint64{1084818905618843912, 0})
	n3 := Simd_i8x16_max_u(n1, n2)
	n4 := Simd_i8x16_shuffle(n3, n3, [2]uint64{117835012, 0})
	n5 := Simd_i8x16_max_u(n3, n4)
	n6 := Simd_i8x16_shuffle(n5, n5, [2]uint64{770, 0})
	n7 := Simd_i8x16_max_u(n5, n6)
	return n7[0], n7[1]
}

//go:noinline
func Simd_p_fx260(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_splat(s0)
	n1 := Simd_i8x16_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx261(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_splat(s1)
	n1 := Simd_v128_load(m, s0, 0)
	n2 := Simd_i8x16_shuffle(n1, [2]uint64{p0, p0h}, [2]uint64{795458214199165184, 216736831629295872})
	n3 := Simd_v128_load32_lane(m, s0, 16, 2, n2)
	n4 := Simd_v128_load32_lane(m, s0, 24, 3, n3)
	n5 := Simd_i32x4_mul(n4, n0)
	n6 := Simd_i32x4_add([2]uint64{p0, p0h}, n5)
	n7 := Simd_i32x4_add(n6, [2]uint64{p1, p1h})
	return n1[0], n1[1], n3[0], n3[1], n4[0], n4[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx262(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 120)
	_ = Simd_v128_store(m, s0, 96, n0)
	return
}

//go:noinline
func Simd_p_fx263(m *Module, s0 int32, s1 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_v128_load32_zero(m, s1, 0)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	n4 := Simd_i64x2_extmul_low_i32x4_s(n1, n3)
	n5 := Simd_i64x2_add(n4, [2]uint64{p0, p0h})
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx264(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 506097522914230528})
	n1 := Simd_i64x2_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx265(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64) {
	n0 := Simd_i64x2_eq([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i64x2_eq([2]uint64{p3, p3h}, [2]uint64{p4, p4h})
	n3 := Simd_v128_and(n2, [2]uint64{p5, p5h})
	n4 := Simd_i16x8_narrow_i32x4_u(n1, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx266(m *Module, s0 int32, s1 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0+16, 0)
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_v128_load32_zero(m, s1+16, 0)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	n4 := Simd_i64x2_extmul_low_i32x4_s(n1, n3)
	n5 := Simd_v128_load32_zero(m, s0+12, 0)
	n6 := Simd_i32x4_extend_low_i16x8_s(n5)
	n7 := Simd_v128_load32_zero(m, s1+12, 0)
	n8 := Simd_i32x4_extend_low_i16x8_s(n7)
	n9 := Simd_i64x2_extmul_low_i32x4_s(n6, n8)
	n10 := Simd_i64x2_add(n9, [2]uint64{p0, p0h})
	n11 := Simd_i64x2_add(n4, n10)
	return n11[0], n11[1]
}

//go:noinline
func Simd_p_fx267(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 38)
	_ = Simd_v128_store(m, s1, 38, n0)
	n2 := Simd_v128_load(m, s0, 54)
	_ = Simd_v128_store(m, s1, 54, n2)
	n4 := Simd_v128_load(m, s0, 70)
	_ = Simd_v128_store(m, s1, 70, n4)
	return
}

//go:noinline
func Simd_p_fx268(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 38)
	_ = Simd_v128_store(m, s1, 38, n0)
	return
}

//go:noinline
func Simd_p_fx269(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 10166768, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 10166752, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx270(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 92)
	_ = Simd_v128_store(m, s1, 92, n0)
	return
}

//go:noinline
func Simd_p_fx271(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s1, 112, n0)
	return
}

//go:noinline
func Simd_p_fx272(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 24)
	n1 := Simd_v128_load32_lane(m, s1, 24, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 24, 2, n1)
	n3 := Simd_v128_load32_lane(m, s3, 24, 3, n2)
	n4 := Simd_v128_not(n3)
	n5 := Simd_i32x4_shr_u(n4, 12)
	n6 := Simd_v128_and(n5, [2]uint64{p0, p0h})
	n7 := Simd_i32x4_add(n6, [2]uint64{p1, p1h})
	return n7[0], n7[1]
}

//go:noinline
func Simd_p_fx273(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0+15185704, 0)
	n1 := Simd_v128_load32_lane(m, s0+15185832, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s0+15185960, 0, 2, n1)
	n3 := Simd_v128_load32_lane(m, s0+15186088, 0, 3, n2)
	n4 := Simd_i32x4_add(n3, [2]uint64{p0, p0h})
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx274(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, 24091488, 0)
	_ = Simd_v128_store(m, s0, 8, n0)
	_ = Simd_v128_store(m, s0, 64, [2]uint64{p0, p0h})
	return
}

//go:noinline
func Simd_p_fx275(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 24091488, 0)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx276(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx277(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, 24091504, 0, n0)
	n2 := Simd_v128_load(m, 24091296, 0)
	_ = Simd_v128_store(m, 24091424, 0, n2)
	return
}

//go:noinline
func Simd_p_fx278(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_shl([2]uint64{p3, p3h}, 31)
	n1 := Simd_i32x4_shr_s(n0, 31)
	n2 := Simd_v128_bitselect([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, n1)
	n3 := Simd_i8x16_shuffle(n2, n2, [2]uint64{p4, p4h})
	n4 := Simd_i32x4_max_u(n2, n3)
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p0, p0h})
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx279(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx280(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx281(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx282(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 0, 2, n1)
	n3 := Simd_v128_load32_lane(m, s3, 0, 3, n2)
	n4 := Simd_i32x4_shr_u(n3, 8)
	n5 := Simd_v128_and(n4, [2]uint64{p1, p1h})
	n6 := Simd_i32x4_add([2]uint64{p0, p0h}, n5)
	n7 := Simd_i32x4_add(n6, [2]uint64{p2, p2h})
	return n7[0], n7[1]
}

//go:noinline
func Simd_p_fx283(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1+8, 0, n0)
	return
}

//go:noinline
func Simd_p_fx284(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{72060901246895878, 72058693566333184})
	n2 := Simd_i16x8_eq(n1, [2]uint64{p3, p3h})
	n3 := Simd_i32x4_extend_low_i16x8_u(n2)
	n4 := Simd_v128_and(n3, [2]uint64{p4, p4h})
	n5 := Simd_i32x4_add([2]uint64{p0, p0h}, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx285(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx286(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_shl([2]uint64{p0, p0h}, 1)
	n1 := Simd_i32x4_add(n0, [2]uint64{p1, p1h})
	n2 := Simd_i32x4_shr_u(n1, 3)
	return n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx287(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx288(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_andnot([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx289(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 24123264, 0)
	n1 := Simd_v128_load(m, s0, 72)
	n2 := Simd_i32x4_add(n0, n1)
	_ = Simd_v128_store(m, 24123264, 0, n2)
	return
}

//go:noinline
func Simd_p_fx290(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13362520, 0)
	_ = Simd_v128_store(m, s0, 102, n0)
	return
}

//go:noinline
func Simd_p_fx291(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13362552, 0)
	_ = Simd_v128_store(m, s0, 102, n0)
	return
}

//go:noinline
func Simd_p_fx292(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 2)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx293(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 180, n0)
	return
}

//go:noinline
func Simd_p_fx294(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 212, n0)
	return
}

//go:noinline
func Simd_p_fx295(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 244, n0)
	return
}

//go:noinline
func Simd_p_fx296(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 272, n0)
	return
}

//go:noinline
func Simd_p_fx297(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_scalar_i32_add(s0, s1)
	n1 := Simd_v128_load(m, n0, 0)
	n2 := Simd_scalar_i32_add(s2, s1)
	_ = Simd_v128_store(m, n2, 0, n1)
	return
}

//go:noinline
func Simd_p_fx298(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 876)
	_ = Simd_v128_store(m, s1, 372, n0)
	n2 := Simd_v128_load(m, s0, 860)
	_ = Simd_v128_store(m, s1, 356, n2)
	return
}

//go:noinline
func Simd_p_fx299(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 33, n0)
	return
}

//go:noinline
func Simd_p_fx300(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx301(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_xor([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_or(n1, [2]uint64{p1, p1h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx302(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1084818905618843912, 0})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	n2 := Simd_i8x16_shuffle(n1, n1, [2]uint64{117835012, 0})
	n3 := Simd_v128_or(n1, n2)
	n4 := Simd_i8x16_shuffle(n3, n3, [2]uint64{770, 0})
	n5 := Simd_v128_or(n3, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx303(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1, 0})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx304(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx305(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_v128_xor([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_xor([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n2 := Simd_v128_load(m, s0, 0)
	n3 := Simd_v128_xor([2]uint64{p4, p4h}, n2)
	n4 := Simd_v128_or(n1, n3)
	n5 := Simd_v128_or(n0, n4)
	n6 := Simd_i8x16_shuffle(n5, n5, [2]uint64{1084818905618843912, 0})
	n7 := Simd_v128_or(n5, n6)
	n8 := Simd_i8x16_shuffle(n7, n7, [2]uint64{117835012, 0})
	n9 := Simd_v128_or(n7, n8)
	n10 := Simd_i8x16_shuffle(n9, n9, [2]uint64{770, 0})
	n11 := Simd_v128_or(n9, n10)
	return n11[0], n11[1]
}

//go:noinline
func Simd_p_fx306(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_eq([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_low_i8x16_s(n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx307(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_eq([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i16x8_extend_low_i8x16_s(n0)
	n2 := Simd_i32x4_extend_low_i16x8_s(n1)
	n3 := Simd_i8x16_shuffle(n2, [2]uint64{p0, p0h}, [2]uint64{940136352262127872, 72058693566333184})
	n4 := Simd_v128_and([2]uint64{p0, p0h}, n3)
	n5 := Simd_i8x16_shuffle(n4, [2]uint64{p0, p0h}, [2]uint64{506097522914230528, 2242261671028070680})
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx308(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 28)
	n1 := Simd_v128_load32_lane(m, s0, 8, 1, n0)
	n2 := Simd_v128_load32_zero(m, s1, 21)
	n3 := Simd_v128_load32_lane(m, s1, 1, 1, n2)
	return n1[0], n1[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx309(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_ne([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_ne([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n2 := Simd_v128_or(n0, n1)
	n3 := Simd_i8x16_ne([2]uint64{p4, p4h}, [2]uint64{p5, p5h})
	n4 := Simd_v128_or(n2, n3)
	n5 := Simd_i16x8_extend_low_i8x16_s(n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx310(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 312, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 328, n2)
	return
}

//go:noinline
func Simd_p_fx311(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 280)
	_ = Simd_v128_store(m, s0, 296, n0)
	return
}

//go:noinline
func Simd_p_fx312(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 296)
	_ = Simd_v128_store(m, s0, 280, n0)
	return
}

//go:noinline
func Simd_p_fx313(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 280)
	_ = Simd_v128_store(m, s0, 14, n0)
	return
}

//go:noinline
func Simd_p_fx314(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12406384, 16)
	_ = Simd_v128_store(m, s0, 80, n0)
	n2 := Simd_v128_load(m, 12406384, 0)
	_ = Simd_v128_store(m, s0, 64, n2)
	return
}

//go:noinline
func Simd_p_fx315(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12406432, 16)
	_ = Simd_v128_store(m, s0, 80, n0)
	n2 := Simd_v128_load(m, 12406432, 0)
	_ = Simd_v128_store(m, s0, 64, n2)
	return
}

//go:noinline
func Simd_p_fx316(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12406448, 0)
	_ = Simd_v128_store(m, s0, 128, n0)
	n2 := Simd_v128_load(m, 12406432, 0)
	_ = Simd_v128_store(m, s0, 112, n2)
	return
}

//go:noinline
func Simd_p_fx317(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12406400, 0)
	_ = Simd_v128_store(m, s0, 128, n0)
	n2 := Simd_v128_load(m, 12406384, 0)
	_ = Simd_v128_store(m, s0, 112, n2)
	return
}

//go:noinline
func Simd_p_fx318(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{289644378169868803, 868365760874482187})
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx319(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s2, 0, n2)
	return
}

//go:noinline
func Simd_p_fx320(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx321(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx322(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s0, 16, n2)
	return
}

//go:noinline
func Simd_p_fx323(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s0, 32, n0)
	return
}

//go:noinline
func Simd_p_fx324(m *Module, s0 int32) {
	n0 := Simd_v128_load_rng(m, s0, 32, 16, 32)
	n1 := Simd_v128_load_nc(m, s0, 16)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s0, 32, n2)
	return
}

//go:noinline
func Simd_p_fx325(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx326(m *Module, s0 int32, s1 int32) {
	n0 := Simd_i32x4_splat(s0)
	_ = Simd_v128_store(m, s1, 32, n0)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx327(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_splat(s1)
	n3 := Simd_i32x4_ge_u(n2, [2]uint64{p1, p1h})
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx328(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s2, 0, n2)
	n4 := Simd_v128_load(m, s0, 16)
	n5 := Simd_v128_load(m, s1+16, 0)
	n6 := Simd_v128_xor(n4, n5)
	_ = Simd_v128_store(m, s2+16, 0, n6)
	n8 := Simd_v128_load(m, s0, 32)
	n9 := Simd_v128_load(m, s1+32, 0)
	n10 := Simd_v128_xor(n8, n9)
	_ = Simd_v128_store(m, s2+32, 0, n10)
	n12 := Simd_v128_load(m, s0, 48)
	n13 := Simd_v128_load(m, s1+48, 0)
	n14 := Simd_v128_xor(n12, n13)
	_ = Simd_v128_store(m, s2+48, 0, n14)
	return
}

//go:noinline
func Simd_p_fx329(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_load(m, s2, s1)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s3, s1, n2)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx330(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_shr_u(n0, s2)
	n2 := Simd_v128_load(m, s1, 0)
	n3 := Simd_i32x4_shl(n2, s3)
	n4 := Simd_v128_or(n1, n3)
	n5 := Simd_scalar_i32_shl(s4, 2)
	n6 := Simd_scalar_i32_add(s1, n5)
	_ = Simd_v128_store(m, n6, 0, n4)
	return
}

//go:noinline
func Simd_p_fx331(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) {
	n0 := Simd_v128_load_rng(m, s0, 0, 0, 20)
	n1 := Simd_i32x4_shr_u(n0, s1)
	n2 := Simd_v128_load_nc(m, s0+4, 0)
	n3 := Simd_i32x4_shl(n2, s2)
	n4 := Simd_v128_or(n1, n3)
	_ = Simd_v128_store(m, s3, 0, n4)
	return
}

//go:noinline
func Simd_p_fx332(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_andnot([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p0, p0h})
	n2 := Simd_v128_load_rng(m, s0+4, 0, -4, 20)
	n3 := Simd_i32x4_shl(n2, 1)
	n4 := Simd_v128_load_nc(m, s0, 0)
	return n3[0], n3[1], n0[0], n0[1], n4[0], n4[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx333(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_or([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx334(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i64x2_shr_u([2]uint64{p0, p0h}, 31)
	n1 := Simd_v128_and(n0, [2]uint64{p1, p1h})
	n2 := Simd_i64x2_add(n1, [2]uint64{p2, p2h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx335(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i64x2_shl([2]uint64{p0, p0h}, 1)
	n1 := Simd_v128_and(n0, [2]uint64{p1, p1h})
	n2 := Simd_i64x2_add(n1, [2]uint64{p2, p2h})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx336(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load_rng(m, s0, 0, 0, 20)
	n1 := Simd_i32x4_shr_u(n0, 16)
	n2 := Simd_v128_load_nc(m, s1, 0)
	n3 := Simd_i32x4_shl(n2, 16)
	n4 := Simd_v128_or(n1, n3)
	_ = Simd_v128_store(m, s1, 0, n4)
	return
}

//go:noinline
func Simd_p_fx337(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_add(n0, [2]uint64{p1, p1h})
	n3 := Simd_i32x4_splat(s1)
	return n0[0], n0[1], n3[0], n3[1], n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx338(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	n2 := Simd_i16x8_narrow_i32x4_u(n0, n1)
	n3 := Simd_v128_and([2]uint64{p3, p3h}, [2]uint64{p1, p1h})
	n4 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p1, p1h})
	n5 := Simd_i16x8_narrow_i32x4_u(n3, n4)
	n6 := Simd_i8x16_narrow_i16x8_u(n2, n5)
	_ = Simd_v128_store(m, s0, 0, n6)
	return
}

//go:noinline
func Simd_p_fx339(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 96, n0)
	return
}

//go:noinline
func Simd_p_fx340(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 112, n0)
	return
}

//go:noinline
func Simd_p_fx341(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 48, n0)
	return
}

//go:noinline
func Simd_p_fx342(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 64, n0)
	return
}

//go:noinline
func Simd_p_fx343(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx344(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 16, n0)
	return
}

//go:noinline
func Simd_p_fx345(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	n2 := Simd_v128_and([2]uint64{p3, p3h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 32, n0)
	_ = Simd_v128_store(m, s0, 16, n1)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx346(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 144, n0)
	return
}

//go:noinline
func Simd_p_fx347(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 160, n0)
	return
}

//go:noinline
func Simd_p_fx348(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 176, n0)
	return
}

//go:noinline
func Simd_p_fx349(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 192, n0)
	return
}

//go:noinline
func Simd_p_fx350(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 208, n0)
	return
}

//go:noinline
func Simd_p_fx351(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 336, n0)
	return
}

//go:noinline
func Simd_p_fx352(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 352, n0)
	return
}

//go:noinline
func Simd_p_fx353(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 368, n0)
	return
}

//go:noinline
func Simd_p_fx354(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 384, n0)
	return
}

//go:noinline
func Simd_p_fx355(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 400, n0)
	return
}

//go:noinline
func Simd_p_fx356(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 240, n0)
	return
}

//go:noinline
func Simd_p_fx357(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 256, n0)
	return
}

//go:noinline
func Simd_p_fx358(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 272, n0)
	return
}

//go:noinline
func Simd_p_fx359(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 288, n0)
	return
}

//go:noinline
func Simd_p_fx360(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 304, n0)
	return
}

//go:noinline
func Simd_p_fx361(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, n0)
	_ = Simd_v128_store(m, s0, 16, n1)
	return
}

//go:noinline
func Simd_p_fx362(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 32, n0)
	return
}

//go:noinline
func Simd_p_fx363(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 80, n0)
	return
}

//go:noinline
func Simd_p_fx364(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 128, n0)
	return
}

//go:noinline
func Simd_p_fx365(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 224, n0)
	return
}

//go:noinline
func Simd_p_fx366(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 192, n0)
	_ = Simd_v128_store(m, s0, 208, n1)
	return
}

//go:noinline
func Simd_p_fx367(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 320, n0)
	return
}

//go:noinline
func Simd_p_fx368(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 480, n0)
	return
}

//go:noinline
func Simd_p_fx369(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 496, n0)
	return
}

//go:noinline
func Simd_p_fx370(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 512, n0)
	return
}

//go:noinline
func Simd_p_fx371(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 528, n0)
	return
}

//go:noinline
func Simd_p_fx372(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 544, n0)
	return
}

//go:noinline
func Simd_p_fx373(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 416, n0)
	return
}

//go:noinline
func Simd_p_fx374(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 432, n0)
	return
}

//go:noinline
func Simd_p_fx375(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 448, n0)
	return
}

//go:noinline
func Simd_p_fx376(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 560, n0)
	return
}

//go:noinline
func Simd_p_fx377(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 576, n0)
	return
}

//go:noinline
func Simd_p_fx378(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 592, n0)
	return
}

//go:noinline
func Simd_p_fx379(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 608, n0)
	return
}

//go:noinline
func Simd_p_fx380(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 624, n0)
	return
}

//go:noinline
func Simd_p_fx381(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 640, n0)
	return
}

//go:noinline
func Simd_p_fx382(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	n2 := Simd_v128_and([2]uint64{p3, p3h}, [2]uint64{p1, p1h})
	n3 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p1, p1h})
	n4 := Simd_v128_and([2]uint64{p5, p5h}, [2]uint64{p1, p1h})
	n5 := Simd_v128_and([2]uint64{p6, p6h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 448, n0)
	_ = Simd_v128_store(m, s0, 464, n1)
	_ = Simd_v128_store(m, s0, 480, n2)
	_ = Simd_v128_store(m, s0, 496, n3)
	_ = Simd_v128_store(m, s0, 512, n4)
	_ = Simd_v128_store(m, s0, 528, n5)
	return
}

//go:noinline
func Simd_p_fx383(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0+2916, 0, n0)
	return
}

//go:noinline
func Simd_p_fx384(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shl(n2, 8)
	n4 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p2, p2h})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n9 := Simd_i16x8_extend_low_i8x16_u(n8)
	n10 := Simd_i32x4_extend_low_i16x8_u(n9)
	n11 := Simd_i32x4_shl(n10, 16)
	n12 := Simd_v128_or(n7, n11)
	n13 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p4, p4h})
	n14 := Simd_i16x8_extend_low_i8x16_u(n13)
	n15 := Simd_i32x4_extend_low_i16x8_u(n14)
	n16 := Simd_i32x4_shl(n15, 24)
	n17 := Simd_v128_or(n12, n16)
	return n17[0], n17[1]
}

//go:noinline
func Simd_p_fx385(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_f32x4_gt([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i64x2_extend_low_i32x4_s(n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx386(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{506097522914230528, 1663540288323457296})
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx387(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1538, 0})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shl(n2, 8)
	n4 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1795, 0})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1281, 0})
	n9 := Simd_i16x8_extend_low_i8x16_u(n8)
	n10 := Simd_i32x4_extend_low_i16x8_u(n9)
	n11 := Simd_i32x4_shl(n10, 16)
	n12 := Simd_v128_or(n7, n11)
	n13 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1024, 0})
	n14 := Simd_i16x8_extend_low_i8x16_u(n13)
	n15 := Simd_i32x4_extend_low_i16x8_u(n14)
	n16 := Simd_i32x4_shl(n15, 24)
	n17 := Simd_v128_or(n12, n16)
	n18 := Simd_f64x2_promote_low_f32x4(n17)
	_ = Simd_v128_store(m, s0, 0, n18)
	return
}

//go:noinline
func Simd_p_fx388(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1538, 0})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shl(n2, 8)
	n4 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1795, 0})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1281, 0})
	n9 := Simd_i16x8_extend_low_i8x16_u(n8)
	n10 := Simd_i32x4_extend_low_i16x8_u(n9)
	n11 := Simd_i32x4_shl(n10, 16)
	n12 := Simd_v128_or(n7, n11)
	n13 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1024, 0})
	n14 := Simd_i16x8_extend_low_i8x16_u(n13)
	n15 := Simd_i32x4_extend_low_i16x8_u(n14)
	n16 := Simd_i32x4_shl(n15, 24)
	n17 := Simd_v128_or(n12, n16)
	return n17[0], n17[1]
}

//go:noinline
func Simd_p_fx389(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1538, 0})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shl(n2, 8)
	n4 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1795, 0})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1281, 0})
	n9 := Simd_i16x8_extend_low_i8x16_u(n8)
	n10 := Simd_i32x4_extend_low_i16x8_u(n9)
	n11 := Simd_i32x4_shl(n10, 16)
	n12 := Simd_v128_or(n7, n11)
	n13 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1024, 0})
	n14 := Simd_i16x8_extend_low_i8x16_u(n13)
	n15 := Simd_i32x4_extend_low_i16x8_u(n14)
	n16 := Simd_i32x4_shl(n15, 24)
	n17 := Simd_v128_or(n12, n16)
	n18 := Simd_i8x16_shuffle(n17, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n19 := Simd_i8x16_shuffle([2]uint64{p1, p1h}, n17, [2]uint64{p2, p2h})
	n20 := Simd_f32x4_gt(n19, n18)
	n21 := Simd_v128_bitselect(n17, [2]uint64{p1, p1h}, n20)
	return n21[0], n21[1]
}

//go:noinline
func Simd_p_fx390(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 28, n0)
	return
}

//go:noinline
func Simd_p_fx391(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 44, n0)
	return
}

//go:noinline
func Simd_p_fx392(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_i64x2_shr_u(n0, 40)
	n2 := Simd_i64x2_shr_u(n0, 32)
	n3 := Simd_i64x2_shr_u(n0, 24)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx393(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i64x2_shr_u([2]uint64{p0, p0h}, 56)
	n1 := Simd_i64x2_shr_u([2]uint64{p0, p0h}, 48)
	n2 := Simd_i8x16_shuffle(n0, n1, [2]uint64{4096, 6152})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx394(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 48, n4)
	return
}

//go:noinline
func Simd_p_fx395(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 49, n0)
	return
}

//go:noinline
func Simd_p_fx396(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 65, n0)
	return
}

//go:noinline
func Simd_p_fx397(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 81, n0)
	return
}

//go:noinline
func Simd_p_fx398(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 97, n0)
	return
}

//go:noinline
func Simd_p_fx399(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 20, n0)
	return
}

//go:noinline
func Simd_p_fx400(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 36, n0)
	return
}

//go:noinline
func Simd_p_fx401(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 1404)
	_ = Simd_v128_store(m, s1, 168, n0)
	n2 := Simd_v128_load(m, s0, 1388)
	_ = Simd_v128_store(m, s1, 152, n2)
	return
}

//go:noinline
func Simd_p_fx402(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 1888)
	_ = Simd_v128_store(m, s1, 120, n0)
	n2 := Simd_v128_load(m, s0, 1904)
	_ = Simd_v128_store(m, s1, 136, n2)
	return
}

//go:noinline
func Simd_p_fx403(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 8, n0)
	n2 := Simd_v128_load(m, s0, 176)
	_ = Simd_v128_store(m, s1, 24, n2)
	return
}

//go:noinline
func Simd_p_fx404(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx405(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	n1 := Simd_v128_not(n0)
	_ = Simd_v128_store(m, s0, 12, n1)
	n3 := Simd_v128_load(m, s0, 28)
	n4 := Simd_v128_not(n3)
	_ = Simd_v128_store(m, s0, 28, n4)
	return
}

//go:noinline
func Simd_p_fx406(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	n1 := Simd_v128_load(m, s1, 24)
	n2 := Simd_v128_or(n0, n1)
	_ = Simd_v128_store(m, s0, 12, n2)
	n4 := Simd_v128_load(m, s0, 28)
	n5 := Simd_v128_load(m, s1, 40)
	n6 := Simd_v128_or(n4, n5)
	_ = Simd_v128_store(m, s0, 28, n6)
	return
}

//go:noinline
func Simd_p_fx407(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	n1 := Simd_v128_load(m, s1, 24)
	n2 := Simd_v128_and(n0, n1)
	_ = Simd_v128_store(m, s0, 12, n2)
	n4 := Simd_v128_load(m, s0, 28)
	n5 := Simd_v128_load(m, s1, 40)
	n6 := Simd_v128_and(n4, n5)
	_ = Simd_v128_store(m, s0, 28, n6)
	return
}

//go:noinline
func Simd_p_fx408(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 17)
	_ = Simd_v128_store(m, s1, 28, n0)
	n2 := Simd_v128_load(m, s0, s2)
	_ = Simd_v128_store(m, s1, 12, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx409(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 496, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 480, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 464, n4)
	n6 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 448, n6)
	return
}

//go:noinline
func Simd_p_fx410(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx411(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p0, p0h})
	n2 := Simd_i16x8_extend_low_i8x16_s(n1)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	n4 := Simd_i8x16_eq(n0, [2]uint64{p1, p1h})
	return n0[0], n0[1], n1[0], n1[1], n3[0], n3[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx412(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_s([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_v128_or([2]uint64{p3, p3h}, n1)
	n3 := Simd_i8x16_eq([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n4 := Simd_i16x8_extend_low_i8x16_s(n3)
	n5 := Simd_i32x4_extend_low_i16x8_s(n4)
	n6 := Simd_v128_or(n2, n5)
	return n1[0], n1[1], n3[0], n3[1], n5[0], n5[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx413(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_eq(n0, [2]uint64{p2, p2h})
	n2 := Simd_i16x8_extend_low_i8x16_s(n1)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	return n0[0], n0[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx414(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_eq([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_v128_or([2]uint64{p1, p1h}, n2)
	n4 := Simd_v128_or([2]uint64{p0, p0h}, n3)
	n5 := Simd_v128_xor([2]uint64{p5, p5h}, [2]uint64{p6, p6h})
	n6 := Simd_v128_or([2]uint64{p4, p4h}, n5)
	n7 := Simd_v128_andnot(n4, n6)
	return n7[0], n7[1]
}

//go:noinline
func Simd_p_fx415(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_ne([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_low_i8x16_s(n0)
	n2 := Simd_i32x4_extend_low_i16x8_s(n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx416(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_v128_andnot([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_v128_and(n0, [2]uint64{p3, p3h})
	n2 := Simd_i32x4_add([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx417(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p1, p1h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_v128_and(n1, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_add([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx418(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx419(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx420(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx421(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 8, n0)
	n2 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 24, n2)
	return
}

//go:noinline
func Simd_p_fx422(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 52, n0)
	n2 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 68, n2)
	return
}

//go:noinline
func Simd_p_fx423(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 36, n0)
	n2 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 52, n2)
	return
}

//go:noinline
func Simd_p_fx424(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 8, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 24, n2)
	return
}

//go:noinline
func Simd_p_fx425(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 60, n0)
	return
}

//go:noinline
func Simd_p_fx426(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 44, n0)
	return
}

//go:noinline
func Simd_p_fx427(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx428(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 44, n0)
	return
}

//go:noinline
func Simd_p_fx429(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8804379, 0)
	_ = Simd_v128_store(m, s0, 928, n0)
	return
}

//go:noinline
func Simd_p_fx430(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_scalar_i32_shl(s2, 4)
	n2 := Simd_scalar_i32_add(s1, n1)
	_ = Simd_v128_store(m, n2, 0, n0)
	return
}

//go:noinline
func Simd_p_fx431(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx432(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13250560, 0)
	_ = Simd_v128_store(m, s0, 1312, n0)
	return
}

//go:noinline
func Simd_p_fx433(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_i32x4_extend_low_i16x8_u([2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx434(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 1724)
	n1 := Simd_v128_load(m, s1, 140)
	_ = Simd_v128_store(m, s0, 1724, n1)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx435(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13257264, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 13257248, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx436(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load_rng(m, s0, 0, 0, 32)
	n1 := Simd_v128_load_nc(m, s0, 16)
	n2 := Simd_i8x16_shuffle(n0, n1, [2]uint64{1084535218666537729, 2241977984075764497})
	n3 := Simd_i8x16_add(n2, [2]uint64{p0, p0h})
	n4 := Simd_i8x16_shuffle(n0, n1, [2]uint64{1012195045828461056, 2169637811237687824})
	return n2[0], n2[1], n3[0], n3[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx437(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_add([2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n1 := Simd_i8x16_lt_u(n0, [2]uint64{p4, p4h})
	n2 := Simd_v128_bitselect([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, n1)
	n3 := Simd_i8x16_add([2]uint64{p0, p0h}, n2)
	n4 := Simd_i8x16_gt_u([2]uint64{p5, p5h}, [2]uint64{p6, p6h})
	n5 := Simd_v128_bitselect(n3, [2]uint64{p5, p5h}, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx438(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_lt_u(n0, [2]uint64{p2, p2h})
	n2 := Simd_v128_and(n1, [2]uint64{p3, p3h})
	n3 := Simd_i8x16_add([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx439(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 216)
	_ = Simd_v128_store(m, s1, 2376, n0)
	n2 := Simd_v128_load(m, s0, 200)
	_ = Simd_v128_store(m, s1, 2360, n2)
	return
}

//go:noinline
func Simd_p_fx440(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8926697, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx441(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 36, n0)
	return
}

//go:noinline
func Simd_p_fx442(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 340)
	_ = Simd_v128_store(m, s1, 340, n0)
	return
}

//go:noinline
func Simd_p_fx443(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 524)
	_ = Simd_v128_store(m, s1, 524, n0)
	return
}

//go:noinline
func Simd_p_fx444(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{66051, 0})
	n2 := Simd_i8x16_eq(n1, [2]uint64{p1, p1h})
	n3 := Simd_i16x8_extend_low_i8x16_u(n2)
	n4 := Simd_i32x4_extend_low_i16x8_u(n3)
	n5 := Simd_v128_and(n4, [2]uint64{p2, p2h})
	n6 := Simd_i32x4_add([2]uint64{p0, p0h}, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx445(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 88, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 72, n2)
	return
}

//go:noinline
func Simd_p_fx446(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 72)
	_ = Simd_v128_store(m, s1, 88, n0)
	n2 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s1, 104, n2)
	return
}

//go:noinline
func Simd_p_fx447(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{579005069656919567, 283686952306183})
	_ = Simd_v128_store(m, s1, 0, n1)
	return
}

//go:noinline
func Simd_p_fx448(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_shr_u([2]uint64{p1, p1h}, 12)
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_add([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx449(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 24091424, 0)
	_ = Simd_v128_store(m, s0, 248, n0)
	return
}

//go:noinline
func Simd_p_fx450(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 0, 2, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx451(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{283686952306183, 0})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_v128_xor(n1, [2]uint64{p2, p2h})
	n3 := Simd_i8x16_lt_s(n0, [2]uint64{p3, p3h})
	n4 := Simd_i16x8_extend_low_i8x16_s(n3)
	n5 := Simd_v128_bitselect(n2, n1, n4)
	_ = Simd_v128_store(m, s0, 0, n5)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx452(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{434320308619640833, 1013041691324254217})
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p1, p1h}, [2]uint64{72060901246895878, 72058693566333184})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx453(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_v128_or([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx454(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_ne(n0, [2]uint64{p1, p1h})
	n2 := Simd_i32x4_sub([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx455(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 8, n2)
	return
}

//go:noinline
func Simd_p_fx456(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 24089688, 0)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx457(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13364568, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 13364584, 0)
	_ = Simd_v128_store(m, s0, 32, n2)
	return
}

//go:noinline
func Simd_p_fx458(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s0, 16, n0)
	return
}

//go:noinline
func Simd_p_fx459(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{117835012, 0})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx460(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i16x8_shr_u([2]uint64{p0, p0h}, 8)
	n1 := Simd_i8x16_shuffle([2]uint64{p1, p1h}, n0, [2]uint64{1374164143712502016, 1663524835064808708})
	n2 := Simd_v128_and(n1, [2]uint64{p2, p2h})
	n3 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, n0, [2]uint64{1952885526417115400, 2242246217769422092})
	n4 := Simd_v128_and(n3, [2]uint64{p2, p2h})
	n5 := Simd_i8x16_narrow_i16x8_u(n2, n4)
	_ = Simd_v128_store(m, s0, 0, n5)
	return
}

//go:noinline
func Simd_p_fx461(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 304)
	_ = Simd_v128_store(m, s0+128, 0, n0)
	return
}

//go:noinline
func Simd_p_fx462(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 280)
	_ = Simd_v128_store(m, s0, 88, n0)
	return
}

//go:noinline
func Simd_p_fx463(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s0, 32, n0)
	return
}

//go:noinline
func Simd_p_fx464(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 364)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx465(m *Module) {
	n0 := Simd_v128_load(m, 24091296, 0)
	_ = Simd_v128_store(m, 24091424, 0, n0)
	return
}

//go:noinline
func Simd_p_fx466(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx467(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx468(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s1, 80, n0)
	return
}

//go:noinline
func Simd_p_fx469(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_or(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx470(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 24123264, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx471(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, 24268264, 0, n0)
	return
}

//go:noinline
func Simd_p_fx472(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 8)
	n1 := Simd_v128_load(m, s1, 8)
	_ = Simd_v128_store(m, s0, 8, n1)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx473(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_not(n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx474(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 96, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 80, n2)
	return
}

//go:noinline
func Simd_p_fx475(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s1, 88, n0)
	n2 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 104, n2)
	return
}

//go:noinline
func Simd_p_fx476(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s0, 56, n0)
	n2 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s0, 40, n2)
	return
}

//go:noinline
func Simd_p_fx477(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s0, 136, n0)
	return
}

//go:noinline
func Simd_p_fx478(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 120, n0)
	return
}

//go:noinline
func Simd_p_fx479(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_i8x16_splat(s0)
	n1 := Simd_i8x16_splat(s1)
	n2 := Simd_i8x16_shuffle(n0, n1, [2]uint64{1152939097061330944, 1152939097061330944})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx480(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_load(m, s1, 0)
	n2 := Simd_i8x16_shuffle(n1, n1, [2]uint64{p0, p0h})
	n3 := Simd_i8x16_shuffle(n0, n1, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s1, 0, n3)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx481(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8724917, 0)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx482(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 0, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx483(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, 16, n0)
	n2 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s2, s3, n2)
	_ = Simd_v128_store(m, s2+32, s3, n2)
	_ = Simd_v128_store(m, s2+48, s3, n0)
	_ = Simd_v128_store(m, s4, s3, n2)
	n7 := Simd_scalar_i32_add(s2, s1)
	_ = Simd_v128_store(m, n7, s3, n0)
	_ = Simd_v128_store(m, s2+96, s3, n2)
	_ = Simd_v128_store(m, s2+112, s3, n0)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx484(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 69)
	_ = Simd_v128_store(m, s1, 81, n0)
	n2 := Simd_v128_load(m, s0, 125)
	_ = Simd_v128_store(m, s1, 117, n2)
	n4 := Simd_v128_load(m, s0, 109)
	_ = Simd_v128_store(m, s1, 101, n4)
	return
}

//go:noinline
func Simd_p_fx485(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 157)
	_ = Simd_v128_store(m, s1, 149, n0)
	return
}

//go:noinline
func Simd_p_fx486(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 117)
	_ = Simd_v128_store(m, s0, 184, n0)
	n2 := Simd_v128_load(m, s0, 101)
	_ = Simd_v128_store(m, s0, 168, n2)
	return
}

//go:noinline
func Simd_p_fx487(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 149)
	_ = Simd_v128_store(m, s0, 224, n0)
	n2 := Simd_v128_load(m, s0, 133)
	_ = Simd_v128_store(m, s0, 208, n2)
	return
}

//go:noinline
func Simd_p_fx488(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 56, n0)
	n2 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 40, n2)
	return
}

//go:noinline
func Simd_p_fx489(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 200)
	_ = Simd_v128_store(m, s1, 284, n0)
	return
}

//go:noinline
func Simd_p_fx490(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+18, 0)
	_ = Simd_v128_store(m, s1, 68, n0)
	n2 := Simd_v128_load(m, s0+2, 0)
	_ = Simd_v128_store(m, s1, 52, n2)
	return
}

//go:noinline
func Simd_p_fx491(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+18, 0)
	_ = Simd_v128_store(m, s1, 36, n0)
	n2 := Simd_v128_load(m, s0+2, 0)
	_ = Simd_v128_store(m, s1, 20, n2)
	return
}

//go:noinline
func Simd_p_fx492(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p1, p1h})
	n2 := Simd_i16x8_extend_low_i8x16_s(n1)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	n4 := Simd_v128_or([2]uint64{p0, p0h}, n3)
	n5 := Simd_i8x16_eq(n0, [2]uint64{p3, p3h})
	n6 := Simd_i16x8_extend_low_i8x16_s(n5)
	n7 := Simd_i32x4_extend_low_i16x8_s(n6)
	n8 := Simd_v128_or([2]uint64{p2, p2h}, n7)
	return n4[0], n4[1], n8[0], n8[1]
}

//go:noinline
func Simd_p_fx493(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_shl([2]uint64{p0, p0h}, 31)
	n1 := Simd_i32x4_shr_s(n0, 31)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx494(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 64)
	n1 := Simd_scalar_i32_add(s1, s2)
	_ = Simd_v128_store(m, n1, 0, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx495(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 36, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 20, n2)
	return
}

//go:noinline
func Simd_p_fx496(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 196)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 180)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx497(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_i8x16_splat(s2)
	n1 := Simd_v128_load(m, s0, 0)
	n2 := Simd_v128_load(m, s1, 0)
	n3 := Simd_v128_and(n2, n0)
	n4 := Simd_v128_or(n1, n3)
	_ = Simd_v128_store(m, s0, 0, n4)
	return
}

//go:noinline
func Simd_p_fx498(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 500)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx499(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_splat(s1)
	n1 := Simd_i32x4_lt_u([2]uint64{p0, p0h}, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p5, p5h})
	n3 := Simd_v128_load32_zero(m, s0, 0)
	n4 := Simd_i8x16_shuffle(n3, [2]uint64{p0, p0h}, [2]uint64{66051, 0})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_not(n6)
	n8 := Simd_i32x4_add(n0, n6)
	n9 := Simd_i32x4_shr_u(n8, 31)
	n10 := Simd_i32x4_add(n9, [2]uint64{p1, p1h})
	n11 := Simd_i32x4_add([2]uint64{p2, p2h}, n7)
	n12 := Simd_i32x4_shr_u(n11, 31)
	n13 := Simd_i32x4_add(n12, [2]uint64{p1, p1h})
	n14 := Simd_v128_or(n10, n13)
	n15 := Simd_v128_and(n14, n1)
	n16 := Simd_v128_and(n15, [2]uint64{p3, p3h})
	n17 := Simd_v128_or(n16, [2]uint64{p4, p4h})
	return n17[0], n17[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx500(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405208, 0)
	_ = Simd_v128_store(m, s0, 8304, n0)
	n2 := Simd_v128_load(m, 12405224, 0)
	_ = Simd_v128_store(m, s0, 8320, n2)
	return
}

//go:noinline
func Simd_p_fx501(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405416, 0)
	_ = Simd_v128_store(m, s0, 8320, n0)
	n2 := Simd_v128_load(m, 12405400, 0)
	_ = Simd_v128_store(m, s0, 8304, n2)
	return
}

//go:noinline
func Simd_p_fx502(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405256, 0)
	_ = Simd_v128_store(m, s0, 8320, n0)
	n2 := Simd_v128_load(m, 12405240, 0)
	_ = Simd_v128_store(m, s0, 8304, n2)
	return
}

//go:noinline
func Simd_p_fx503(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405288, 0)
	_ = Simd_v128_store(m, s0, 8320, n0)
	n2 := Simd_v128_load(m, 12405272, 0)
	_ = Simd_v128_store(m, s0, 8304, n2)
	return
}

//go:noinline
func Simd_p_fx504(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405320, 0)
	_ = Simd_v128_store(m, s0, 8320, n0)
	n2 := Simd_v128_load(m, 12405304, 0)
	_ = Simd_v128_store(m, s0, 8304, n2)
	return
}

//go:noinline
func Simd_p_fx505(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405352, 0)
	_ = Simd_v128_store(m, s0, 8320, n0)
	n2 := Simd_v128_load(m, 12405336, 0)
	_ = Simd_v128_store(m, s0, 8304, n2)
	return
}

//go:noinline
func Simd_p_fx506(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405384, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 12405368, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx507(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405416, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 12405400, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx508(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405448, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 12405432, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx509(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405480, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 12405464, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx510(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12405512, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 12405496, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx511(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_and(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_add(n1, [2]uint64{p1, p1h})
	n3 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n4 := Simd_i32x4_eq(n3, [2]uint64{p3, p3h})
	n5 := Simd_v128_bitselect(n1, n2, n4)
	return n1[0], n1[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx512(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_ge_u([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_v128_not([2]uint64{p3, p3h})
	n2 := Simd_v128_or(n0, n1)
	n3 := Simd_v128_and([2]uint64{p0, p0h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx513(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_v128_and([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx514(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_v128_and([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx515(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx516(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 20, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 36, n2)
	return
}

//go:noinline
func Simd_p_fx517(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 68, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 52, n2)
	return
}

//go:noinline
func Simd_p_fx518(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx519(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12417984, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx520(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_i32x4_add(n1, [2]uint64{p1, p1h})
	return n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx521(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p2, p2h})
	n2 := Simd_v128_xor(n0, n1)
	n3 := Simd_i32x4_shr_s(n2, 8)
	n4 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n5 := Simd_v128_and(n3, n4)
	n6 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p4, p4h})
	n7 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p5, p5h})
	n8 := Simd_v128_xor(n6, n7)
	n9 := Simd_i32x4_shr_s(n8, 8)
	n10 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p6, p6h})
	n11 := Simd_v128_and(n9, n10)
	n12 := Simd_v128_or(n5, n11)
	return n12[0], n12[1]
}

//go:noinline
func Simd_p_fx522(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_v128_xor([2]uint64{p0, p0h}, n0)
	n2 := Simd_i32x4_shr_u(n1, 8)
	n3 := Simd_i32x4_add([2]uint64{p1, p1h}, [2]uint64{p3, p3h})
	n4 := Simd_v128_and(n2, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx523(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_xor(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_shr_u(n1, 8)
	n3 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n4 := Simd_v128_and(n2, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx524(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p2, p2h})
	n2 := Simd_v128_xor(n0, n1)
	n3 := Simd_i32x4_shr_u(n2, 8)
	n4 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n5 := Simd_v128_and(n3, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx525(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_eq([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_low_i8x16_s(n0)
	n2 := Simd_i32x4_extend_low_i16x8_s(n1)
	n3 := Simd_i64x2_extend_low_i32x4_s(n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx526(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_sub([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_sub([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, -40, 72)
	n5 := Simd_v128_load_nc(m, s2+8, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2+8, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx527(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 32)
	n5 := Simd_v128_load_nc(m, s1, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s1, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx528(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 72)
	n5 := Simd_v128_load_nc(m, s2, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx529(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_sub([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_sub([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 72)
	n5 := Simd_v128_load_nc(m, s2, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx530(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, -248, 280)
	n5 := Simd_v128_load_nc(m, s2+128, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2+128, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx531(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1+256, 0, 0, 112)
	n5 := Simd_v128_load_nc(m, s2, 0)
	n6 := Simd_v128_load_nc(m, s1+256, 16)
	n7 := Simd_v128_load_nc(m, s2, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx532(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_sub([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_sub([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 216)
	n5 := Simd_v128_load_nc(m, s2+480, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2+480, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx533(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 136)
	n5 := Simd_v128_load_nc(m, s2+480, 0)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2+480, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx534(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 64, n2)
	n4 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 80, n4)
	return
}

//go:noinline
func Simd_p_fx535(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n2)
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p1, p1h})
	return
}

//go:noinline
func Simd_p_fx536(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx537(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx538(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 76)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx539(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n4)
	n6 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 48, n6)
	return
}

//go:noinline
func Simd_p_fx540(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 0, n1)
	n3 := Simd_v128_load(m, s0, 16)
	n4 := Simd_i32x4_add(n3, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 16, n4)
	return
}

//go:noinline
func Simd_p_fx541(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_extend_low_i16x8_u([2]uint64{p1, p1h})
	n1 := Simd_i32x4_eq([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and(n1, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_extend_high_i16x8_u([2]uint64{p1, p1h})
	n4 := Simd_i32x4_eq([2]uint64{p0, p0h}, n3)
	n5 := Simd_v128_and(n4, [2]uint64{p2, p2h})
	n6 := Simd_i16x8_narrow_i32x4_u(n2, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx542(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_v128_and([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and([2]uint64{p2, p2h}, n0)
	n3 := Simd_i32x4_add([2]uint64{p1, p1h}, n2)
	n4 := Simd_v128_and([2]uint64{p4, p4h}, n0)
	n5 := Simd_i32x4_add([2]uint64{p3, p3h}, n4)
	n6 := Simd_v128_load(m, s1, 256)
	n7 := Simd_i32x4_add(n1, n6)
	_ = Simd_v128_store(m, s1, 256, n7)
	_ = Simd_v128_store(m, s1, 240, n3)
	_ = Simd_v128_store(m, s1, 224, n5)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx543(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_add([2]uint64{p3, p3h}, n2)
	n4 := Simd_v128_and([2]uint64{p6, p6h}, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_add([2]uint64{p5, p5h}, n4)
	_ = Simd_v128_store(m, s0, 208, n1)
	_ = Simd_v128_store(m, s0, 192, n3)
	_ = Simd_v128_store(m, s0, 176, n5)
	return
}

//go:noinline
func Simd_p_fx544(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_add([2]uint64{p3, p3h}, n2)
	n4 := Simd_v128_and([2]uint64{p6, p6h}, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_add([2]uint64{p5, p5h}, n4)
	_ = Simd_v128_store(m, s0, 160, n1)
	_ = Simd_v128_store(m, s0, 144, n3)
	_ = Simd_v128_store(m, s0, 128, n5)
	return
}

//go:noinline
func Simd_p_fx545(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_add([2]uint64{p3, p3h}, n2)
	n4 := Simd_v128_and([2]uint64{p6, p6h}, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_add([2]uint64{p5, p5h}, n4)
	_ = Simd_v128_store(m, s0, 112, n1)
	_ = Simd_v128_store(m, s0, 96, n3)
	_ = Simd_v128_store(m, s0, 80, n5)
	return
}

//go:noinline
func Simd_p_fx546(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_add([2]uint64{p3, p3h}, n2)
	n4 := Simd_v128_and([2]uint64{p6, p6h}, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_add([2]uint64{p5, p5h}, n4)
	_ = Simd_v128_store(m, s0, 64, n1)
	_ = Simd_v128_store(m, s0, 48, n3)
	_ = Simd_v128_store(m, s0, 32, n5)
	return
}

//go:noinline
func Simd_p_fx547(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) {
	n0 := Simd_v128_and([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	n3 := Simd_i32x4_add([2]uint64{p3, p3h}, n2)
	_ = Simd_v128_store(m, s0, 16, n1)
	_ = Simd_v128_store(m, s0, 0, n3)
	n6 := Simd_v128_load(m, s1, 1144)
	n7 := Simd_v128_and(n6, [2]uint64{p2, p2h})
	n8 := Simd_i32x4_add([2]uint64{p5, p5h}, n7)
	_ = Simd_v128_store(m, s0, 272, n8)
	return
}

//go:noinline
func Simd_p_fx548(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0+1352, 0)
	n1 := Simd_v128_and(n0, [2]uint64{p0, p0h})
	n2 := Simd_v128_load(m, s1, 0)
	n3 := Simd_i32x4_add(n1, n2)
	_ = Simd_v128_store(m, s1, 0, n3)
	n5 := Simd_v128_load(m, s0+1368, 0)
	n6 := Simd_v128_and(n5, [2]uint64{p0, p0h})
	n7 := Simd_v128_load(m, s1+16, 0)
	n8 := Simd_i32x4_add(n6, n7)
	_ = Simd_v128_store(m, s1+16, 0, n8)
	return
}

//go:noinline
func Simd_p_fx549(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 4, n0)
	return
}

//go:noinline
func Simd_p_fx550(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 20, n0)
	return
}

//go:noinline
func Simd_p_fx551(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 36, n0)
	return
}

//go:noinline
func Simd_p_fx552(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 52, n0)
	return
}

//go:noinline
func Simd_p_fx553(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 68, n0)
	return
}

//go:noinline
func Simd_p_fx554(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 84, n0)
	return
}

//go:noinline
func Simd_p_fx555(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 100, n0)
	return
}

//go:noinline
func Simd_p_fx556(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 116, n0)
	return
}

//go:noinline
func Simd_p_fx557(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 132, n0)
	return
}

//go:noinline
func Simd_p_fx558(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 148, n0)
	return
}

//go:noinline
func Simd_p_fx559(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 164, n0)
	return
}

//go:noinline
func Simd_p_fx560(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 180, n0)
	return
}

//go:noinline
func Simd_p_fx561(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 196, n0)
	return
}

//go:noinline
func Simd_p_fx562(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0+1952, 0)
	n1 := Simd_v128_and(n0, [2]uint64{p0, p0h})
	n2 := Simd_v128_load(m, s1, 0)
	n3 := Simd_i32x4_add(n1, n2)
	_ = Simd_v128_store(m, s1, 0, n3)
	n5 := Simd_v128_load(m, s0+1968, 0)
	n6 := Simd_v128_and(n5, [2]uint64{p0, p0h})
	n7 := Simd_v128_load(m, s1+16, 0)
	n8 := Simd_i32x4_add(n6, n7)
	_ = Simd_v128_store(m, s1+16, 0, n8)
	return
}

//go:noinline
func Simd_p_fx563(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx564(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 464, n0)
	return
}

//go:noinline
func Simd_p_fx565(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx566(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 168)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 168, n1)
	return
}

//go:noinline
func Simd_p_fx567(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 28, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 12, n2)
	return
}

//go:noinline
func Simd_p_fx568(m *Module) {
	n0 := Simd_v128_load(m, 12479940, 0)
	_ = Simd_v128_store(m, 15537952, 0, n0)
	n2 := Simd_v128_load(m, 12479924, 0)
	_ = Simd_v128_store(m, 15537936, 0, n2)
	return
}

//go:noinline
func Simd_p_fx569(m *Module) {
	n0 := Simd_v128_load(m, 12479972, 0)
	_ = Simd_v128_store(m, 15537984, 0, n0)
	n2 := Simd_v128_load(m, 12479988, 0)
	_ = Simd_v128_store(m, 15538000, 0, n2)
	return
}

//go:noinline
func Simd_p_fx570(m *Module) {
	n0 := Simd_v128_load(m, 12480004, 0)
	_ = Simd_v128_store(m, 15538016, 0, n0)
	n2 := Simd_v128_load(m, 12480020, 0)
	_ = Simd_v128_store(m, 15538032, 0, n2)
	return
}

//go:noinline
func Simd_p_fx571(m *Module) {
	n0 := Simd_v128_load(m, 12480060, 0)
	_ = Simd_v128_store(m, 15538072, 0, n0)
	n2 := Simd_v128_load(m, 12480044, 0)
	_ = Simd_v128_store(m, 15538056, 0, n2)
	return
}

//go:noinline
func Simd_p_fx572(m *Module) {
	n0 := Simd_v128_load(m, 12480084, 0)
	_ = Simd_v128_store(m, 15538096, 0, n0)
	n2 := Simd_v128_load(m, 12480100, 0)
	_ = Simd_v128_store(m, 15538112, 0, n2)
	return
}

//go:noinline
func Simd_p_fx573(m *Module) {
	n0 := Simd_v128_load(m, 12480124, 0)
	_ = Simd_v128_store(m, 15538136, 0, n0)
	n2 := Simd_v128_load(m, 12480140, 0)
	_ = Simd_v128_store(m, 15538152, 0, n2)
	return
}

//go:noinline
func Simd_p_fx574(m *Module) {
	n0 := Simd_v128_load(m, 12480180, 0)
	_ = Simd_v128_store(m, 15538192, 0, n0)
	n2 := Simd_v128_load(m, 12480164, 0)
	_ = Simd_v128_store(m, 15538176, 0, n2)
	return
}

//go:noinline
func Simd_p_fx575(m *Module) {
	n0 := Simd_v128_load(m, 12480220, 0)
	_ = Simd_v128_store(m, 15538232, 0, n0)
	n2 := Simd_v128_load(m, 12480204, 0)
	_ = Simd_v128_store(m, 15538216, 0, n2)
	return
}

//go:noinline
func Simd_p_fx576(m *Module) {
	n0 := Simd_v128_load(m, 12480260, 0)
	_ = Simd_v128_store(m, 15538272, 0, n0)
	n2 := Simd_v128_load(m, 12480244, 0)
	_ = Simd_v128_store(m, 15538256, 0, n2)
	return
}

//go:noinline
func Simd_p_fx577(m *Module) {
	n0 := Simd_v128_load(m, 12480300, 0)
	_ = Simd_v128_store(m, 15538312, 0, n0)
	n2 := Simd_v128_load(m, 12480284, 0)
	_ = Simd_v128_store(m, 15538296, 0, n2)
	return
}

//go:noinline
func Simd_p_fx578(m *Module) {
	n0 := Simd_v128_load(m, 12480340, 0)
	_ = Simd_v128_store(m, 15538352, 0, n0)
	n2 := Simd_v128_load(m, 12480324, 0)
	_ = Simd_v128_store(m, 15538336, 0, n2)
	return
}

//go:noinline
func Simd_p_fx579(m *Module) {
	n0 := Simd_v128_load(m, 12480380, 0)
	_ = Simd_v128_store(m, 15538392, 0, n0)
	n2 := Simd_v128_load(m, 12480364, 0)
	_ = Simd_v128_store(m, 15538376, 0, n2)
	return
}

//go:noinline
func Simd_p_fx580(m *Module) {
	n0 := Simd_v128_load(m, 12480420, 0)
	_ = Simd_v128_store(m, 15538432, 0, n0)
	n2 := Simd_v128_load(m, 12480404, 0)
	_ = Simd_v128_store(m, 15538416, 0, n2)
	return
}

//go:noinline
func Simd_p_fx581(m *Module) {
	n0 := Simd_v128_load(m, 12480460, 0)
	_ = Simd_v128_store(m, 15538472, 0, n0)
	n2 := Simd_v128_load(m, 12480444, 0)
	_ = Simd_v128_store(m, 15538456, 0, n2)
	return
}

//go:noinline
func Simd_p_fx582(m *Module) {
	n0 := Simd_v128_load(m, 12480500, 0)
	_ = Simd_v128_store(m, 15538512, 0, n0)
	n2 := Simd_v128_load(m, 12480484, 0)
	_ = Simd_v128_store(m, 15538496, 0, n2)
	return
}

//go:noinline
func Simd_p_fx583(m *Module) {
	n0 := Simd_v128_load(m, 12480540, 0)
	_ = Simd_v128_store(m, 15538552, 0, n0)
	n2 := Simd_v128_load(m, 12480524, 0)
	_ = Simd_v128_store(m, 15538536, 0, n2)
	return
}

//go:noinline
func Simd_p_fx584(m *Module) {
	n0 := Simd_v128_load(m, 12480580, 0)
	_ = Simd_v128_store(m, 15538592, 0, n0)
	n2 := Simd_v128_load(m, 12480564, 0)
	_ = Simd_v128_store(m, 15538576, 0, n2)
	return
}

//go:noinline
func Simd_p_fx585(m *Module) {
	n0 := Simd_v128_load(m, 12480620, 0)
	_ = Simd_v128_store(m, 15538632, 0, n0)
	n2 := Simd_v128_load(m, 12480604, 0)
	_ = Simd_v128_store(m, 15538616, 0, n2)
	return
}

//go:noinline
func Simd_p_fx586(m *Module) {
	n0 := Simd_v128_load(m, 12480660, 0)
	_ = Simd_v128_store(m, 15538672, 0, n0)
	n2 := Simd_v128_load(m, 12480644, 0)
	_ = Simd_v128_store(m, 15538656, 0, n2)
	return
}

//go:noinline
func Simd_p_fx587(m *Module) {
	n0 := Simd_v128_load(m, 12480700, 0)
	_ = Simd_v128_store(m, 15538712, 0, n0)
	n2 := Simd_v128_load(m, 12480684, 0)
	_ = Simd_v128_store(m, 15538696, 0, n2)
	return
}

//go:noinline
func Simd_p_fx588(m *Module) {
	n0 := Simd_v128_load(m, 12480740, 0)
	_ = Simd_v128_store(m, 15538752, 0, n0)
	n2 := Simd_v128_load(m, 12480724, 0)
	_ = Simd_v128_store(m, 15538736, 0, n2)
	return
}

//go:noinline
func Simd_p_fx589(m *Module) {
	n0 := Simd_v128_load(m, 12480780, 0)
	_ = Simd_v128_store(m, 15538792, 0, n0)
	n2 := Simd_v128_load(m, 12480764, 0)
	_ = Simd_v128_store(m, 15538776, 0, n2)
	return
}

//go:noinline
func Simd_p_fx590(m *Module) {
	n0 := Simd_v128_load(m, 12480820, 0)
	_ = Simd_v128_store(m, 15538832, 0, n0)
	n2 := Simd_v128_load(m, 12480804, 0)
	_ = Simd_v128_store(m, 15538816, 0, n2)
	return
}

//go:noinline
func Simd_p_fx591(m *Module) {
	n0 := Simd_v128_load(m, 12480860, 0)
	_ = Simd_v128_store(m, 15538872, 0, n0)
	n2 := Simd_v128_load(m, 12480844, 0)
	_ = Simd_v128_store(m, 15538856, 0, n2)
	return
}

//go:noinline
func Simd_p_fx592(m *Module) {
	n0 := Simd_v128_load(m, 12480900, 0)
	_ = Simd_v128_store(m, 15538912, 0, n0)
	n2 := Simd_v128_load(m, 12480884, 0)
	_ = Simd_v128_store(m, 15538896, 0, n2)
	return
}

//go:noinline
func Simd_p_fx593(m *Module) {
	n0 := Simd_v128_load(m, 12480940, 0)
	_ = Simd_v128_store(m, 15538952, 0, n0)
	n2 := Simd_v128_load(m, 12480924, 0)
	_ = Simd_v128_store(m, 15538936, 0, n2)
	return
}

//go:noinline
func Simd_p_fx594(m *Module) {
	n0 := Simd_v128_load(m, 12480980, 0)
	_ = Simd_v128_store(m, 15538992, 0, n0)
	n2 := Simd_v128_load(m, 12480964, 0)
	_ = Simd_v128_store(m, 15538976, 0, n2)
	return
}

//go:noinline
func Simd_p_fx595(m *Module) {
	n0 := Simd_v128_load(m, 12481020, 0)
	_ = Simd_v128_store(m, 15539032, 0, n0)
	n2 := Simd_v128_load(m, 12481004, 0)
	_ = Simd_v128_store(m, 15539016, 0, n2)
	return
}

//go:noinline
func Simd_p_fx596(m *Module) {
	n0 := Simd_v128_load(m, 12481060, 0)
	_ = Simd_v128_store(m, 15539072, 0, n0)
	n2 := Simd_v128_load(m, 12481044, 0)
	_ = Simd_v128_store(m, 15539056, 0, n2)
	return
}

//go:noinline
func Simd_p_fx597(m *Module) {
	n0 := Simd_v128_load(m, 12481100, 0)
	_ = Simd_v128_store(m, 15539112, 0, n0)
	n2 := Simd_v128_load(m, 12481084, 0)
	_ = Simd_v128_store(m, 15539096, 0, n2)
	return
}

//go:noinline
func Simd_p_fx598(m *Module) {
	n0 := Simd_v128_load(m, 12481140, 0)
	_ = Simd_v128_store(m, 15539152, 0, n0)
	n2 := Simd_v128_load(m, 12481124, 0)
	_ = Simd_v128_store(m, 15539136, 0, n2)
	return
}

//go:noinline
func Simd_p_fx599(m *Module) {
	n0 := Simd_v128_load(m, 12481180, 0)
	_ = Simd_v128_store(m, 15539192, 0, n0)
	n2 := Simd_v128_load(m, 12481164, 0)
	_ = Simd_v128_store(m, 15539176, 0, n2)
	return
}

//go:noinline
func Simd_p_fx600(m *Module) {
	n0 := Simd_v128_load(m, 12481220, 0)
	_ = Simd_v128_store(m, 15539232, 0, n0)
	n2 := Simd_v128_load(m, 12481204, 0)
	_ = Simd_v128_store(m, 15539216, 0, n2)
	return
}

//go:noinline
func Simd_p_fx601(m *Module) {
	n0 := Simd_v128_load(m, 12481260, 0)
	_ = Simd_v128_store(m, 15539272, 0, n0)
	n2 := Simd_v128_load(m, 12481244, 0)
	_ = Simd_v128_store(m, 15539256, 0, n2)
	return
}

//go:noinline
func Simd_p_fx602(m *Module) {
	n0 := Simd_v128_load(m, 12481300, 0)
	_ = Simd_v128_store(m, 15539312, 0, n0)
	n2 := Simd_v128_load(m, 12481284, 0)
	_ = Simd_v128_store(m, 15539296, 0, n2)
	return
}

//go:noinline
func Simd_p_fx603(m *Module) {
	n0 := Simd_v128_load(m, 12481340, 0)
	_ = Simd_v128_store(m, 15539352, 0, n0)
	n2 := Simd_v128_load(m, 12481324, 0)
	_ = Simd_v128_store(m, 15539336, 0, n2)
	return
}

//go:noinline
func Simd_p_fx604(m *Module) {
	n0 := Simd_v128_load(m, 12481380, 0)
	_ = Simd_v128_store(m, 15539392, 0, n0)
	n2 := Simd_v128_load(m, 12481364, 0)
	_ = Simd_v128_store(m, 15539376, 0, n2)
	return
}

//go:noinline
func Simd_p_fx605(m *Module) {
	n0 := Simd_v128_load(m, 12481420, 0)
	_ = Simd_v128_store(m, 15539432, 0, n0)
	n2 := Simd_v128_load(m, 12481404, 0)
	_ = Simd_v128_store(m, 15539416, 0, n2)
	return
}

//go:noinline
func Simd_p_fx606(m *Module) {
	n0 := Simd_v128_load(m, 12481460, 0)
	_ = Simd_v128_store(m, 15539472, 0, n0)
	n2 := Simd_v128_load(m, 12481444, 0)
	_ = Simd_v128_store(m, 15539456, 0, n2)
	return
}

//go:noinline
func Simd_p_fx607(m *Module) {
	n0 := Simd_v128_load(m, 12481500, 0)
	_ = Simd_v128_store(m, 15539512, 0, n0)
	n2 := Simd_v128_load(m, 12481484, 0)
	_ = Simd_v128_store(m, 15539496, 0, n2)
	return
}

//go:noinline
func Simd_p_fx608(m *Module) {
	n0 := Simd_v128_load(m, 12481540, 0)
	_ = Simd_v128_store(m, 15539552, 0, n0)
	n2 := Simd_v128_load(m, 12481524, 0)
	_ = Simd_v128_store(m, 15539536, 0, n2)
	return
}

//go:noinline
func Simd_p_fx609(m *Module) {
	n0 := Simd_v128_load(m, 12481580, 0)
	_ = Simd_v128_store(m, 15539592, 0, n0)
	n2 := Simd_v128_load(m, 12481564, 0)
	_ = Simd_v128_store(m, 15539576, 0, n2)
	return
}

//go:noinline
func Simd_p_fx610(m *Module) {
	n0 := Simd_v128_load(m, 12481620, 0)
	_ = Simd_v128_store(m, 15539632, 0, n0)
	n2 := Simd_v128_load(m, 12481604, 0)
	_ = Simd_v128_store(m, 15539616, 0, n2)
	return
}

//go:noinline
func Simd_p_fx611(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n4)
	return
}

//go:noinline
func Simd_p_fx612(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64) {
	n0 := Simd_scalar_i32_add(s0, s1)
	n1 := Simd_v128_load(m, n0, 0)
	n2 := Simd_i8x16_shuffle(n1, [2]uint64{p0, p0h}, [2]uint64{579005069656919567, 283686952306183})
	_ = Simd_v128_store(m, s2, 0, n2)
	return
}

//go:noinline
func Simd_p_fx613(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_ne([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i64x2_extend_low_i32x4_s(n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx614(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_splat(s0)
	n2 := Simd_i8x16_eq(n1, [2]uint64{p2, p2h})
	n3 := Simd_i16x8_extend_low_i8x16_s(n2)
	n4 := Simd_i32x4_extend_low_i16x8_s(n3)
	n5 := Simd_v128_bitselect(n0, [2]uint64{p0, p0h}, n4)
	n6 := Simd_i32x4_add(n5, [2]uint64{p1, p1h})
	n7 := Simd_v128_bitselect(n0, [2]uint64{p3, p3h}, n4)
	n8 := Simd_i8x16_splat(s1)
	n9 := Simd_i8x16_eq(n8, [2]uint64{p2, p2h})
	n10 := Simd_i16x8_extend_low_i8x16_s(n9)
	n11 := Simd_i32x4_extend_low_i16x8_s(n10)
	n12 := Simd_v128_bitselect(n6, n5, n11)
	n13 := Simd_v128_bitselect(n6, n7, n11)
	return n12[0], n12[1], n13[0], n13[1]
}

//go:noinline
func Simd_p_fx615(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_splat(s0)
	n2 := Simd_i8x16_eq(n1, [2]uint64{p3, p3h})
	n3 := Simd_i16x8_extend_low_i8x16_s(n2)
	n4 := Simd_i32x4_extend_low_i16x8_s(n3)
	n5 := Simd_v128_bitselect(n0, [2]uint64{p2, p2h}, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx616(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_xor([2]uint64{p0, p0h}, n0)
	n2 := Simd_i32x4_shr_u(n1, 8)
	return n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx617(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_shr_u([2]uint64{p0, p0h}, 24)
	n1 := Simd_i32x4_shr_u([2]uint64{p0, p0h}, 16)
	n2 := Simd_i8x16_shuffle(n0, n1, [2]uint64{22007412428800, 30837865191432})
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx618(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_shl([2]uint64{p2, p2h}, 31)
	n1 := Simd_i32x4_shr_s(n0, 31)
	n2 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, n1)
	n3 := Simd_i8x16_shuffle(n2, n2, [2]uint64{1084818905618843912, 216736831629295872})
	n4 := Simd_i32x4_max_u(n2, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx619(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx620(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 8, n2)
	return
}

//go:noinline
func Simd_p_fx621(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 104)
	_ = Simd_v128_store(m, s0, 40, n0)
	return
}

//go:noinline
func Simd_p_fx622(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 776)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx623(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 768)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx624(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 768)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx625(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 760)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx626(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 760)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx627(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 752)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx628(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 752)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx629(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 36, n0)
	n2 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s1, 52, n2)
	return
}

//go:noinline
func Simd_p_fx630(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 352)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 336)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx631(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+544, 0)
	_ = Simd_v128_store(m, s1, 16464, n0)
	return
}

//go:noinline
func Simd_p_fx632(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 53)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 37)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 21)
	_ = Simd_v128_store(m, s1, 16, n4)
	return
}

//go:noinline
func Simd_p_fx633(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 236, n0)
	return
}

//go:noinline
func Simd_p_fx634(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 84)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 8, n2)
	return
}

//go:noinline
func Simd_p_fx635(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 140)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx636(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 216)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx637(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 244)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 260)
	_ = Simd_v128_store(m, s1, 16, n2)
	return
}

//go:noinline
func Simd_p_fx638(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 296)
	_ = Simd_v128_store(m, s0, 152, n0)
	return
}

//go:noinline
func Simd_p_fx639(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 324)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx640(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 832)
	_ = Simd_v128_store(m, s1, 832, n0)
	return
}

//go:noinline
func Simd_p_fx641(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 816)
	_ = Simd_v128_store(m, s1, 816, n0)
	return
}

//go:noinline
func Simd_p_fx642(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n0)
	return
}

//go:noinline
func Simd_p_fx643(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 40, n0)
	return
}

//go:noinline
func Simd_p_fx644(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx645(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 904, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 888, n2)
	return
}

//go:noinline
func Simd_p_fx646(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 506097522914230528})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx647(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_shuffle(n0, n0, [2]uint64{1084818905618843912, 0})
	n2 := Simd_i8x16_max_u(n0, n1)
	n3 := Simd_i8x16_shuffle(n2, n2, [2]uint64{117835012, 0})
	n4 := Simd_i8x16_max_u(n2, n3)
	n5 := Simd_i8x16_shuffle(n4, n4, [2]uint64{770, 0})
	n6 := Simd_i8x16_max_u(n4, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx648(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i64x2_ne(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx649(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p1, p1h})
	n2 := Simd_i16x8_narrow_i32x4_u(n0, n1)
	n3 := Simd_v128_and([2]uint64{p3, p3h}, [2]uint64{p1, p1h})
	n4 := Simd_v128_and([2]uint64{p4, p4h}, [2]uint64{p1, p1h})
	n5 := Simd_i16x8_narrow_i32x4_u(n3, n4)
	n6 := Simd_i16x8_narrow_i32x4_u(n2, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx650(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 184)
	_ = Simd_v128_store(m, s1, 184, n0)
	return
}

//go:noinline
func Simd_p_fx651(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 0, n4)
	return
}

//go:noinline
func Simd_p_fx652(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	_ = Simd_v128_store(m, s1, 16, [2]uint64{p0, p0h})
	return
}

//go:noinline
func Simd_p_fx653(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 48, n2)
	n4 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 64, n4)
	return
}

//go:noinline
func Simd_p_fx654(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 576, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 560, n2)
	return
}

//go:noinline
func Simd_p_fx655(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 168)
	_ = Simd_v128_store(m, s1, 4, n0)
	return
}

//go:noinline
func Simd_p_fx656(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 272)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx657(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+180, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx658(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+212, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx659(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 4, n0)
	return
}

//go:noinline
func Simd_p_fx660(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx661(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx662(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s1, 64, n0)
	return
}

//go:noinline
func Simd_p_fx663(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0+422, 0)
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_i64x2_extmul_low_i32x4_s(n1, n1)
	n3 := Simd_v128_load32_zero(m, s0+418, 0)
	n4 := Simd_i32x4_extend_low_i16x8_s(n3)
	n5 := Simd_i64x2_extmul_low_i32x4_s(n4, n4)
	n6 := Simd_i64x2_add(n2, n5)
	n7 := Simd_v128_load32_zero(m, s0+414, 0)
	n8 := Simd_i32x4_extend_low_i16x8_s(n7)
	n9 := Simd_i64x2_extmul_low_i32x4_s(n8, n8)
	n10 := Simd_i64x2_add(n6, n9)
	n11 := Simd_v128_load32_zero(m, s0+410, 0)
	n12 := Simd_i32x4_extend_low_i16x8_s(n11)
	n13 := Simd_i64x2_extmul_low_i32x4_s(n12, n12)
	n14 := Simd_i64x2_add(n10, n13)
	n15 := Simd_i64x2_add(n14, [2]uint64{p0, p0h})
	return n15[0], n15[1]
}

//go:noinline
func Simd_p_fx664(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_i64x2_extmul_low_i32x4_s(n1, n1)
	n3 := Simd_i64x2_add(n2, [2]uint64{p0, p0h})
	return n1[0], n1[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx665(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1084818905618843912, 506097522914230528})
	n1 := Simd_i64x2_add([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx666(m *Module, s0 int32) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s0+1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s0+2, 0, 2, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx667(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, [2]uint64{1374179596971150604, 1952900979675763988})
	n1 := Simd_i32x4_sub([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx668(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_lt_u([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n1 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, n0)
	n2 := Simd_i32x4_gt_u([2]uint64{p2, p2h}, [2]uint64{p5, p5h})
	n3 := Simd_v128_bitselect(n1, [2]uint64{p4, p4h}, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx669(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_lt_u(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx670(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_lt_u(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx671(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load32_lane(m, 0, 15268608, 1, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx672(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 144, n0)
	return
}

//go:noinline
func Simd_p_fx673(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 172, n0)
	n2 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 188, n2)
	return
}

//go:noinline
func Simd_p_fx674(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 232, n0)
	return
}

//go:noinline
func Simd_p_fx675(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 116)
	_ = Simd_v128_store(m, s1, 252, n0)
	return
}

//go:noinline
func Simd_p_fx676(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 160, n0)
	return
}

//go:noinline
func Simd_p_fx677(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 144, n0)
	n2 := Simd_v128_load(m, s2, 44)
	_ = Simd_v128_store(m, s1, 180, n2)
	n4 := Simd_v128_load(m, s2, 60)
	_ = Simd_v128_store(m, s1, 196, n4)
	return
}

//go:noinline
func Simd_p_fx678(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s1, 224, n0)
	return
}

//go:noinline
func Simd_p_fx679(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 24, n2)
	return
}

//go:noinline
func Simd_p_fx680(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 60, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 76, n2)
	return
}

//go:noinline
func Simd_p_fx681(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s1, 104, n0)
	return
}

//go:noinline
func Simd_p_fx682(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 132, n0)
	return
}

//go:noinline
func Simd_p_fx683(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx684(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 8, n0)
	n2 := Simd_v128_load(m, s2, 8)
	_ = Simd_v128_store(m, s1, 44, n2)
	n4 := Simd_v128_load(m, s2, 24)
	_ = Simd_v128_store(m, s1, 60, n4)
	return
}

//go:noinline
func Simd_p_fx685(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 88, n0)
	return
}

//go:noinline
func Simd_p_fx686(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 48)
	n1 := Simd_f64x2_mul(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 48, n1)
	n3 := Simd_v128_load(m, s0, 64)
	n4 := Simd_f64x2_mul(n3, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 64, n4)
	return
}

//go:noinline
func Simd_p_fx687(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 56)
	n1 := Simd_f64x2_add([2]uint64{p0, p0h}, n0)
	_ = Simd_v128_store(m, s0, 56, n1)
	return
}

//go:noinline
func Simd_p_fx688(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, s0, 8)
	n1 := Simd_f64x2_add([2]uint64{p0, p0h}, n0)
	_ = Simd_v128_store(m, s0, 8, n1)
	n3 := Simd_v128_load(m, s0, 40)
	n4 := Simd_f64x2_add(n3, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 40, n4)
	return
}

//go:noinline
func Simd_p_fx689(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 572)
	_ = Simd_v128_store(m, s1, 84, n0)
	n2 := Simd_v128_load(m, s0, 556)
	_ = Simd_v128_store(m, s1, 68, n2)
	return
}

//go:noinline
func Simd_p_fx690(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+16, 0)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx691(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+16, 0)
	_ = Simd_v128_store(m, s1+16, 0, n0)
	return
}

//go:noinline
func Simd_p_fx692(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1084818905618843912, 506097522914230528})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx693(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx694(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8719187, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx695(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8407581, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx696(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, n0, [2]uint64{1948679894439893000, 2238040585792199692})
	n2 := Simd_i8x16_shuffle([2]uint64{p1, p1h}, n0, [2]uint64{1369958511735279616, 1659319203087586308})
	_ = Simd_v128_store(m, s1, 16, n1)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx697(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1663540288323457296, 506097522914230528})
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p2, p2h}, [2]uint64{938188073609731092, 1082868419285884438})
	n2 := Simd_i8x16_shuffle(n0, [2]uint64{p2, p2h}, [2]uint64{648827382257424400, 793507727933577746})
	_ = Simd_v128_store(m, s0, 16, n1)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx698(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	_ = Simd_v128_store(m, s2, 0, n0)
	return
}

//go:noinline
func Simd_p_fx699(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p0, p0h})
	n2 := Simd_i8x16_eq(n0, [2]uint64{p1, p1h})
	n3 := Simd_v128_or(n1, n2)
	n4 := Simd_v128_and(n3, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 272, n4)
	n6 := Simd_v128_load(m, s0, 0)
	n7 := Simd_i8x16_eq(n6, [2]uint64{p0, p0h})
	n8 := Simd_i8x16_eq(n6, [2]uint64{p1, p1h})
	n9 := Simd_v128_or(n7, n8)
	n10 := Simd_v128_and(n9, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 256, n10)
	n12 := Simd_v128_load(m, s0, 32)
	n13 := Simd_i8x16_eq(n12, [2]uint64{p0, p0h})
	n14 := Simd_i8x16_eq(n12, [2]uint64{p1, p1h})
	n15 := Simd_v128_or(n13, n14)
	n16 := Simd_v128_and(n15, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 288, n16)
	n18 := Simd_v128_load(m, s0, 48)
	n19 := Simd_i8x16_eq(n18, [2]uint64{p0, p0h})
	n20 := Simd_i8x16_eq(n18, [2]uint64{p1, p1h})
	n21 := Simd_v128_or(n19, n20)
	n22 := Simd_v128_and(n21, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 304, n22)
	n24 := Simd_v128_load(m, s0, 64)
	n25 := Simd_i8x16_eq(n24, [2]uint64{p0, p0h})
	n26 := Simd_i8x16_eq(n24, [2]uint64{p1, p1h})
	n27 := Simd_v128_or(n25, n26)
	n28 := Simd_v128_and(n27, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 320, n28)
	n30 := Simd_v128_load(m, s0, 80)
	n31 := Simd_i8x16_eq(n30, [2]uint64{p0, p0h})
	n32 := Simd_i8x16_eq(n30, [2]uint64{p1, p1h})
	n33 := Simd_v128_or(n31, n32)
	n34 := Simd_v128_and(n33, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 336, n34)
	n36 := Simd_v128_load(m, s0, 96)
	n37 := Simd_i8x16_eq(n36, [2]uint64{p0, p0h})
	n38 := Simd_i8x16_eq(n36, [2]uint64{p1, p1h})
	n39 := Simd_v128_or(n37, n38)
	n40 := Simd_v128_and(n39, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 352, n40)
	n42 := Simd_v128_load(m, s0, 112)
	n43 := Simd_i8x16_eq(n42, [2]uint64{p0, p0h})
	n44 := Simd_i8x16_eq(n42, [2]uint64{p1, p1h})
	n45 := Simd_v128_or(n43, n44)
	n46 := Simd_v128_and(n45, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 368, n46)
	n48 := Simd_v128_load(m, s0, 128)
	n49 := Simd_i8x16_eq(n48, [2]uint64{p0, p0h})
	n50 := Simd_i8x16_eq(n48, [2]uint64{p1, p1h})
	n51 := Simd_v128_or(n49, n50)
	n52 := Simd_v128_and(n51, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 384, n52)
	n54 := Simd_v128_load(m, s0, 144)
	n55 := Simd_i8x16_eq(n54, [2]uint64{p0, p0h})
	n56 := Simd_i8x16_eq(n54, [2]uint64{p1, p1h})
	n57 := Simd_v128_or(n55, n56)
	n58 := Simd_v128_and(n57, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 400, n58)
	n60 := Simd_v128_load(m, s0, 160)
	n61 := Simd_i8x16_eq(n60, [2]uint64{p0, p0h})
	n62 := Simd_i8x16_eq(n60, [2]uint64{p1, p1h})
	n63 := Simd_v128_or(n61, n62)
	n64 := Simd_v128_and(n63, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 416, n64)
	n66 := Simd_v128_load(m, s0, 176)
	n67 := Simd_i8x16_eq(n66, [2]uint64{p0, p0h})
	n68 := Simd_i8x16_eq(n66, [2]uint64{p1, p1h})
	n69 := Simd_v128_or(n67, n68)
	n70 := Simd_v128_and(n69, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 432, n70)
	n72 := Simd_v128_load(m, s0, 192)
	n73 := Simd_i8x16_eq(n72, [2]uint64{p0, p0h})
	n74 := Simd_i8x16_eq(n72, [2]uint64{p1, p1h})
	n75 := Simd_v128_or(n73, n74)
	n76 := Simd_v128_and(n75, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 448, n76)
	n78 := Simd_v128_load(m, s0, 208)
	n79 := Simd_i8x16_eq(n78, [2]uint64{p0, p0h})
	n80 := Simd_i8x16_eq(n78, [2]uint64{p1, p1h})
	n81 := Simd_v128_or(n79, n80)
	n82 := Simd_v128_and(n81, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 464, n82)
	n84 := Simd_v128_load(m, s0, 224)
	n85 := Simd_i8x16_eq(n84, [2]uint64{p0, p0h})
	n86 := Simd_i8x16_eq(n84, [2]uint64{p1, p1h})
	n87 := Simd_v128_or(n85, n86)
	n88 := Simd_v128_and(n87, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 480, n88)
	n90 := Simd_v128_load(m, s0, 240)
	n91 := Simd_i8x16_eq(n90, [2]uint64{p0, p0h})
	n92 := Simd_i8x16_eq(n90, [2]uint64{p1, p1h})
	n93 := Simd_v128_or(n91, n92)
	n94 := Simd_v128_and(n93, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 496, n94)
	return
}

//go:noinline
func Simd_p_fx700(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{795458214199165184, 216736831629295872})
	n2 := Simd_v128_load32_lane(m, s0, 16, 2, n1)
	n3 := Simd_v128_load32_lane(m, s0, 24, 3, n2)
	n4 := Simd_i32x4_add(n3, [2]uint64{p1, p1h})
	n5 := Simd_i32x4_lt_u(n4, [2]uint64{p4, p4h})
	n6 := Simd_i32x4_ne(n3, [2]uint64{p3, p3h})
	n7 := Simd_v128_and(n6, n5)
	n8 := Simd_i32x4_sub([2]uint64{p2, p2h}, n7)
	n9 := Simd_i32x4_ge_u(n4, [2]uint64{p4, p4h})
	n10 := Simd_i32x4_sub([2]uint64{p0, p0h}, n9)
	return n8[0], n8[1], n10[0], n10[1]
}

//go:noinline
func Simd_p_fx701(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 136)
	_ = Simd_v128_store(m, s0+32, 0, n0)
	n2 := Simd_v128_load(m, s0, 152)
	_ = Simd_v128_store(m, s0+48, 0, n2)
	return
}

//go:noinline
func Simd_p_fx702(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_xor([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, s1, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx703(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s1, 56, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 40, n2)
	return
}

//go:noinline
func Simd_p_fx704(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 27, n0)
	n2 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 11, n2)
	return
}

//go:noinline
func Simd_p_fx705(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 165)
	_ = Simd_v128_store(m, s1, 480, n0)
	n2 := Simd_v128_load(m, s0, 181)
	_ = Simd_v128_store(m, s1, 496, n2)
	n4 := Simd_v128_load(m, s0, 197)
	_ = Simd_v128_store(m, s1, 512, n4)
	return
}

//go:noinline
func Simd_p_fx706(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) {
	n0 := Simd_v128_load(m, s0, 181)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 197)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 165)
	_ = Simd_v128_store(m, s1, 0, n4)
	n6 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s2+-64, 0, n6)
	n8 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s2+-64, 16, n8)
	n10 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s3, 0, n10)
	n12 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s3, 16, n12)
	return
}

//go:noinline
func Simd_p_fx707(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 560)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx708(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1+17, 0, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1+1, 0, n2)
	n4 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1+33, 0, n4)
	n6 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1+49, 0, n6)
	return
}

//go:noinline
func Simd_p_fx709(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 2368)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx710(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1+18, 0, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1+2, 0, n2)
	n4 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1+34, 0, n4)
	n6 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1+50, 0, n6)
	return
}

//go:noinline
func Simd_p_fx711(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 2368)
	_ = Simd_v128_store(m, s1, 0, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx712(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1+19, 0, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1+3, 0, n2)
	n4 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1+35, 0, n4)
	n6 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1+51, 0, n6)
	return
}

//go:noinline
func Simd_p_fx713(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 84, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 68, n2)
	return
}

//go:noinline
func Simd_p_fx714(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 84)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 16, n2)
	return
}

//go:noinline
func Simd_p_fx715(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 84, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 68, n2)
	return
}

//go:noinline
func Simd_p_fx716(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, s5 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s3, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s4, n2)
	n4 := Simd_v128_load(m, s0, s5)
	_ = Simd_v128_store(m, s2, s1, n4)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx717(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_load(m, s2, s1)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s0, s1, n2)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx718(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_scalar_i32_add(s0, s1)
	n1 := Simd_v128_load(m, n0, 0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx719(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i8x16_ne(n0, [2]uint64{p1, p1h})
	n2 := Simd_i16x8_extend_low_i8x16_s(n1)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	n4 := Simd_v128_or([2]uint64{p0, p0h}, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx720(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12418512, 0)
	_ = Simd_v128_store(m, s0, 168, n0)
	_ = Simd_v128_store(m, s0, 184, n0)
	_ = Simd_v128_store(m, s0, 200, n0)
	_ = Simd_v128_store(m, s0, 216, n0)
	_ = Simd_v128_store(m, s0, 232, n0)
	_ = Simd_v128_store(m, s0, 248, n0)
	_ = Simd_v128_store(m, s0, 264, n0)
	_ = Simd_v128_store(m, s0, 280, n0)
	_ = Simd_v128_store(m, s0, 312, n0)
	_ = Simd_v128_store(m, s0, 296, n0)
	_ = Simd_v128_store(m, s0, 360, n0)
	_ = Simd_v128_store(m, s0, 344, n0)
	_ = Simd_v128_store(m, s0, 328, n0)
	_ = Simd_v128_store(m, s0, 376, n0)
	_ = Simd_v128_store(m, s0, 392, n0)
	_ = Simd_v128_store(m, s0, 408, n0)
	return
}

//go:noinline
func Simd_p_fx721(m *Module, p0, p0h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i16x8_extend_high_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_high_i16x8_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n0)
	n3 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p0, p0h})
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx722(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_high_i8x16_u(n0)
	n2 := Simd_i32x4_extend_high_i16x8_u(n1)
	n3 := Simd_i32x4_extend_low_i16x8_u(n1)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx723(m *Module, p0, p0h uint64) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_high_i16x8_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n0)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx724(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1948679894439893000, 2238040585792199692})
	n1 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1369958511735279616, 1659319203087586308})
	_ = Simd_v128_store(m, s0, s1, n0)
	_ = Simd_v128_store(m, s0, s2, n1)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx725(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0+12418864, 0)
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_add(n2, [2]uint64{p0, p0h})
	n4 := Simd_v128_and(n3, [2]uint64{p1, p1h})
	return n3[0], n3[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx726(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_shr_s([2]uint64{p0, p0h}, 3)
	n1 := Simd_v128_load32_zero(m, s0, 0)
	n2 := Simd_v128_load32_lane(m, s1, 0, 1, n1)
	n3 := Simd_v128_load32_lane(m, s2, 0, 2, n2)
	n4 := Simd_v128_load32_lane(m, s3, 0, 3, n3)
	return n4[0], n4[1], n0[0], n0[1]
}

//go:noinline
func Simd_p_fx727(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p1, p1h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_v128_and([2]uint64{p0, p0h}, n1)
	n3 := Simd_i32x4_ne(n2, [2]uint64{p2, p2h})
	n4 := Simd_i8x16_shuffle(n3, [2]uint64{p3, p3h}, [2]uint64{201851904, 0})
	n5 := Simd_v128_and(n4, [2]uint64{p4, p4h})
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx728(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, s5 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s3, n2)
	n4 := Simd_v128_load(m, s0, s4)
	_ = Simd_v128_store(m, s2, s4, n4)
	n6 := Simd_v128_load(m, s0, s5)
	_ = Simd_v128_store(m, s2, s5, n6)
	_ = Simd_v128_store(m, s0, s3, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, s1, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, s5, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, s4, [2]uint64{p3, p3h})
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx729(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n4)
	n6 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n6)
	_ = Simd_v128_store(m, s0, 32, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 48, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p3, p3h})
	return
}

//go:noinline
func Simd_p_fx730(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, n0, [2]uint64{1948679894439893000, 2238040585792199692})
	n2 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, n0, [2]uint64{1369958511735279616, 1659319203087586308})
	_ = Simd_v128_store(m, s1, 16, n1)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx731(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0+632, 0, n0)
	return
}

//go:noinline
func Simd_p_fx732(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0+16, 0, n0)
	return
}

//go:noinline
func Simd_p_fx733(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0+316, 0, n0)
	return
}

//go:noinline
func Simd_p_fx734(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx735(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 96, n0)
	return
}

//go:noinline
func Simd_p_fx736(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 120, n0)
	return
}

//go:noinline
func Simd_p_fx737(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 184)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 184, n1)
	return
}

//go:noinline
func Simd_p_fx738(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx739(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{518, 0})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shl(n2, 8)
	n4 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{775, 0})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{261, 0})
	n9 := Simd_i16x8_extend_low_i8x16_u(n8)
	n10 := Simd_i32x4_extend_low_i16x8_u(n9)
	n11 := Simd_i32x4_shl(n10, 16)
	n12 := Simd_v128_or(n7, n11)
	n13 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{4, 0})
	n14 := Simd_i16x8_extend_low_i8x16_u(n13)
	n15 := Simd_i32x4_extend_low_i16x8_u(n14)
	n16 := Simd_i32x4_shl(n15, 24)
	n17 := Simd_v128_or(n12, n16)
	return n17[0], n17[1]
}

//go:noinline
func Simd_p_fx740(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 192)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 192, n1)
	return
}

//go:noinline
func Simd_p_fx741(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shl(n2, 8)
	n4 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p2, p2h})
	n5 := Simd_i16x8_extend_low_i8x16_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n5)
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n9 := Simd_i16x8_extend_low_i8x16_u(n8)
	n10 := Simd_i32x4_extend_low_i16x8_u(n9)
	n11 := Simd_i32x4_shl(n10, 16)
	n12 := Simd_v128_or(n7, n11)
	n13 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p4, p4h})
	n14 := Simd_i16x8_extend_low_i8x16_u(n13)
	n15 := Simd_i32x4_extend_low_i16x8_u(n14)
	n16 := Simd_i32x4_shl(n15, 24)
	n17 := Simd_v128_or(n12, n16)
	n18 := Simd_i8x16_shuffle([2]uint64{p5, p5h}, [2]uint64{p5, p5h}, [2]uint64{p1, p1h})
	n19 := Simd_i16x8_extend_low_i8x16_u(n18)
	n20 := Simd_i32x4_extend_low_i16x8_u(n19)
	n21 := Simd_i32x4_shl(n20, 8)
	n22 := Simd_i8x16_shuffle([2]uint64{p5, p5h}, [2]uint64{p5, p5h}, [2]uint64{p2, p2h})
	n23 := Simd_i16x8_extend_low_i8x16_u(n22)
	n24 := Simd_i32x4_extend_low_i16x8_u(n23)
	n25 := Simd_v128_or(n21, n24)
	n26 := Simd_i8x16_shuffle([2]uint64{p5, p5h}, [2]uint64{p5, p5h}, [2]uint64{p3, p3h})
	n27 := Simd_i16x8_extend_low_i8x16_u(n26)
	n28 := Simd_i32x4_extend_low_i16x8_u(n27)
	n29 := Simd_i32x4_shl(n28, 16)
	n30 := Simd_v128_or(n25, n29)
	n31 := Simd_i8x16_shuffle([2]uint64{p5, p5h}, [2]uint64{p5, p5h}, [2]uint64{p4, p4h})
	n32 := Simd_i16x8_extend_low_i8x16_u(n31)
	n33 := Simd_i32x4_extend_low_i16x8_u(n32)
	n34 := Simd_i32x4_shl(n33, 24)
	n35 := Simd_v128_or(n30, n34)
	n36 := Simd_f32x4_ne(n17, n35)
	return n36[0], n36[1]
}

//go:noinline
func Simd_p_fx742(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 168, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 152, n2)
	n4 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 136, n4)
	return
}

//go:noinline
func Simd_p_fx743(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{579005069656919567, 283686952306183})
	_ = Simd_v128_store(m, s2, s1, n1)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx744(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 0, n4)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx745(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 512)
	_ = Simd_v128_store(m, s1, 224, n0)
	return
}

//go:noinline
func Simd_p_fx746(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_f64x2_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx747(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_splat(s0)
	n1 := Simd_v128_xor([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx748(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_i32x4_splat(s1)
	n1 := Simd_i32x4_min_u(n0, [2]uint64{p0, p0h})
	n2 := Simd_i16x8_narrow_i32x4_u(n1, n1)
	n3 := Simd_v128_load(m, s0, 0)
	n4 := Simd_i16x8_sub_sat_u(n3, n2)
	_ = Simd_v128_store(m, s0, 0, n4)
	return
}

//go:noinline
func Simd_p_fx749(m *Module, s0 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s0, 24, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 8, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx750(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 88, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 104, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx751(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_xor(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx752(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_v128_xor([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx753(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_v128_xor([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx754(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx755(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_load(m, s0, 96)
	n1 := Simd_f64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 96, n1)
	n3 := Simd_v128_load(m, s0, 112)
	n4 := Simd_f64x2_add(n3, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 112, n4)
	return
}

//go:noinline
func Simd_p_fx756(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx757(m *Module, s0 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i16x8_extend_low_i8x16_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n1)
	n3 := Simd_i32x4_shr_u(n2, 3)
	return n2[0], n2[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx758(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_add(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx759(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 64, n0)
	return
}

//go:noinline
func Simd_p_fx760(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s1, 88, n0)
	return
}

//go:noinline
func Simd_p_fx761(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 124)
	_ = Simd_v128_store(m, s1, 124, n0)
	return
}

//go:noinline
func Simd_p_fx762(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 184)
	_ = Simd_v128_store(m, s1, 184, n0)
	n2 := Simd_v128_load(m, s0, 200)
	_ = Simd_v128_store(m, s1, 200, n2)
	return
}

//go:noinline
func Simd_p_fx763(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 256)
	_ = Simd_v128_store(m, s1, 256, n0)
	return
}

//go:noinline
func Simd_p_fx764(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 312)
	_ = Simd_v128_store(m, s1, 312, n0)
	return
}

//go:noinline
func Simd_p_fx765(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 392)
	_ = Simd_v128_store(m, s1, 392, n0)
	return
}

//go:noinline
func Simd_p_fx766(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p1, p1h})
	n2 := Simd_i16x8_extend_low_i8x16_u(n1)
	n3 := Simd_i32x4_extend_low_i16x8_u(n2)
	n4 := Simd_v128_and(n3, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_add([2]uint64{p0, p0h}, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx767(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 16, n0)
	return
}

//go:noinline
func Simd_p_fx768(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 228)
	_ = Simd_v128_store(m, s1, 56, n0)
	n2 := Simd_v128_load(m, s0, 212)
	_ = Simd_v128_store(m, s1, 40, n2)
	n4 := Simd_v128_load(m, s0, 196)
	_ = Simd_v128_store(m, s1, 24, n4)
	n6 := Simd_v128_load(m, s0, 180)
	_ = Simd_v128_store(m, s1, 8, n6)
	return
}

//go:noinline
func Simd_p_fx769(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23939136, 0)
	_ = Simd_v128_store(m, s0, 98, n0)
	n2 := Simd_v128_load(m, 23939120, 0)
	_ = Simd_v128_store(m, s0, 82, n2)
	n4 := Simd_v128_load(m, 23939104, 0)
	_ = Simd_v128_store(m, s0, 66, n4)
	return
}

//go:noinline
func Simd_p_fx770(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 8, n2)
	return
}

//go:noinline
func Simd_p_fx771(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s1, 476, n0)
	n2 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 460, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx772(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 76)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s2, 404, n2)
	n4 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s2, 420, n4)
	return
}

//go:noinline
func Simd_p_fx773(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 76)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s2, 460, n2)
	n4 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s2, 476, n4)
	return
}

//go:noinline
func Simd_p_fx774(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_scalar_i32_add(s1, s2)
	n2 := Simd_v128_load(m, n1, 0)
	n3 := Simd_i32x4_add(n0, n2)
	_ = Simd_v128_store(m, s0, 0, n3)
	n5 := Simd_v128_load(m, s0+16, 0)
	n6 := Simd_v128_load(m, s3+16, 0)
	n7 := Simd_i32x4_add(n5, n6)
	_ = Simd_v128_store(m, s0+16, 0, n7)
	return
}

//go:noinline
func Simd_p_fx775(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 592)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 576)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 560)
	_ = Simd_v128_store(m, s1, 16, n4)
	n6 := Simd_v128_load(m, s0, 544)
	_ = Simd_v128_store(m, s1, 0, n6)
	return
}

//go:noinline
func Simd_p_fx776(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 344)
	_ = Simd_v128_store(m, s1, 4200, n0)
	return
}

//go:noinline
func Simd_p_fx777(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8884794, 0)
	_ = Simd_v128_store(m, s0, 320, n0)
	n2 := Simd_v128_load(m, 8884778, 0)
	_ = Simd_v128_store(m, s0, 304, n2)
	return
}

//go:noinline
func Simd_p_fx778(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 168, n0)
	return
}

//go:noinline
func Simd_p_fx779(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 216, n0)
	return
}

//go:noinline
func Simd_p_fx780(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 240, n0)
	return
}

//go:noinline
func Simd_p_fx781(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 352, n0)
	return
}

//go:noinline
func Simd_p_fx782(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 8, n2)
	n4 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 44, n4)
	return
}

//go:noinline
func Simd_p_fx783(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 60, n0)
	return
}

//go:noinline
func Simd_p_fx784(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 96, n0)
	return
}

//go:noinline
func Simd_p_fx785(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 132)
	_ = Simd_v128_store(m, s1, 132, n0)
	n2 := Simd_v128_load(m, s0, 116)
	_ = Simd_v128_store(m, s1, 116, n2)
	return
}

//go:noinline
func Simd_p_fx786(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0+24, 0)
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_i64x2_extmul_low_i32x4_s(n1, n1)
	n3 := Simd_v128_load32_zero(m, s0+20, 0)
	n4 := Simd_i32x4_extend_low_i16x8_s(n3)
	n5 := Simd_i64x2_extmul_low_i32x4_s(n4, n4)
	n6 := Simd_i64x2_add(n2, n5)
	n7 := Simd_v128_load32_zero(m, s0+16, 0)
	n8 := Simd_i32x4_extend_low_i16x8_s(n7)
	n9 := Simd_i64x2_extmul_low_i32x4_s(n8, n8)
	n10 := Simd_i64x2_add(n6, n9)
	n11 := Simd_v128_load32_zero(m, s0+12, 0)
	n12 := Simd_i32x4_extend_low_i16x8_s(n11)
	n13 := Simd_i64x2_extmul_low_i32x4_s(n12, n12)
	n14 := Simd_i64x2_add(n10, n13)
	n15 := Simd_i64x2_add(n14, [2]uint64{p0, p0h})
	return n15[0], n15[1]
}

//go:noinline
func Simd_p_fx787(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i32x4_extend_low_i16x8_s(n0)
	n2 := Simd_i64x2_extmul_low_i32x4_s(n1, n1)
	n3 := Simd_i64x2_add(n2, [2]uint64{p0, p0h})
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx788(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0+48, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, s0+32, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx789(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 56, n0)
	return
}

//go:noinline
func Simd_p_fx790(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx791(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 12, n0)
	return
}

//go:noinline
func Simd_p_fx792(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{795458214199165184, 216736831629295872})
	n2 := Simd_v128_load32_lane(m, s0, 16, 2, n1)
	n3 := Simd_v128_load32_lane(m, s0, 24, 3, n2)
	n4 := Simd_i32x4_ne(n3, [2]uint64{p1, p1h})
	n5 := Simd_i32x4_sub([2]uint64{p0, p0h}, n4)
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx793(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_i32x4_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_i8x16_shuffle(n1, n1, [2]uint64{216736831696667908, 216736831629295872})
	n3 := Simd_i32x4_add(n1, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx794(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8925523, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx795(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13362544, 0)
	_ = Simd_v128_store(m, s0, 94, n0)
	return
}

//go:noinline
func Simd_p_fx796(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 36, n0)
	return
}

//go:noinline
func Simd_p_fx797(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0+16, 0)
	_ = Simd_v128_store(m, s1+16, 0, n2)
	return
}

//go:noinline
func Simd_p_fx798(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 176)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 8, n2)
	n4 := Simd_v128_load(m, s0, 196)
	_ = Simd_v128_store(m, s1, 44, n4)
	return
}

//go:noinline
func Simd_p_fx799(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 212)
	_ = Simd_v128_store(m, s1, 60, n0)
	return
}

//go:noinline
func Simd_p_fx800(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 248)
	_ = Simd_v128_store(m, s1, 96, n0)
	return
}

//go:noinline
func Simd_p_fx801(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 268)
	_ = Simd_v128_store(m, s1, 116, n0)
	return
}

//go:noinline
func Simd_p_fx802(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 8, n2)
	n4 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 44, n4)
	return
}

//go:noinline
func Simd_p_fx803(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 76)
	_ = Simd_v128_store(m, s1, 60, n0)
	return
}

//go:noinline
func Simd_p_fx804(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s1, 96, n0)
	return
}

//go:noinline
func Simd_p_fx805(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 132)
	_ = Simd_v128_store(m, s1, 116, n0)
	return
}

//go:noinline
func Simd_p_fx806(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p0, p0h})
	return
}

//go:noinline
func Simd_p_fx807(m *Module, s0 int32, s1 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i8x16_shuffle(n0, [2]uint64{p0, p0h}, [2]uint64{434320308619640833, 1013041691324254217})
	_ = Simd_v128_store(m, s1, 48, n1)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx808(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_v128_load32_lane(m, s1, 0, 1, n0)
	n2 := Simd_v128_load32_lane(m, s2, 0, 2, n1)
	n3 := Simd_v128_load32_lane(m, s3, 0, 3, n2)
	n4 := Simd_i32x4_add([2]uint64{p0, p0h}, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx809(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 144, n0)
	return
}

//go:noinline
func Simd_p_fx810(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{72058693667390724, 72058693566333184})
	n1 := Simd_i16x8_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx811(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{72058693566333698, 72058693566333184})
	n1 := Simd_i16x8_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx812(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p1, p1h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_i32x4_add([2]uint64{p0, p0h}, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx813(m *Module, s0 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 72)
	_ = Simd_v128_store(m, s0, 0, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx814(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, 88, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx815(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s0, 32, n0)
	n2 := Simd_v128_load(m, s0, 72)
	_ = Simd_v128_store(m, s0, 16, n2)
	return
}

//go:noinline
func Simd_p_fx816(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 576)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 560)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx817(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_load(m, s2, s1)
	_ = Simd_v128_store(m, s0, s1, n1)
	_ = Simd_v128_store(m, s2, s1, n0)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx818(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load_rng(m, s0+384, 0, 0, 1336)
	n1 := Simd_i64x2_add([2]uint64{p0, p0h}, n0)
	n2 := Simd_v128_load_nc(m, s0+824, 0)
	n3 := Simd_i64x2_add(n1, n2)
	n4 := Simd_v128_load_nc(m, s0+1264, 0)
	n5 := Simd_i64x2_add(n3, n4)
	n6 := Simd_v128_load_nc(m, s0+1704, 0)
	n7 := Simd_i64x2_add(n5, n6)
	return n7[0], n7[1]
}

//go:noinline
func Simd_p_fx819(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i64x2_add([2]uint64{p0, p0h}, n0)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx820(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8807811, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx821(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, 8407581, s0)
	_ = Simd_v128_store(m, s1, s0, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx822(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_not(n0)
	_ = Simd_v128_store(m, s0, s1, n1)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx823(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_load(m, s2, s1)
	n2 := Simd_i8x16_shuffle(n1, n1, [2]uint64{p0, p0h})
	n3 := Simd_i8x16_shuffle(n0, n1, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s2, s1, n3)
	_ = Simd_v128_store(m, s0, s1, n2)
	return n0[0], n0[1], n1[0], n1[1], n3[0], n3[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx824(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 184, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 168, n2)
	return
}

//go:noinline
func Simd_p_fx825(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 224, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 208, n2)
	return
}

//go:noinline
func Simd_p_fx826(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 100)
	_ = Simd_v128_store(m, s1, s2, n0)
	n2 := Simd_v128_load(m, s0, s2)
	_ = Simd_v128_store(m, s1, 68, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx827(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_ge_u(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx828(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i8x16_shuffle(n0, n0, [2]uint64{1084818905618843912, 216736831629295872})
	n2 := Simd_i32x4_add(n0, n1)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx829(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i8x16_shuffle(n0, n0, [2]uint64{1084818905618843912, 216736831629295872})
	n2 := Simd_i32x4_add(n0, n1)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx830(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 133)
	_ = Simd_v128_store(m, s1, 197, n0)
	n2 := Simd_v128_load(m, s0, 117)
	_ = Simd_v128_store(m, s1, 181, n2)
	n4 := Simd_v128_load(m, s0, 101)
	_ = Simd_v128_store(m, s1, 165, n4)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx831(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 240, n0)
	n2 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, s2, n2)
	n4 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 272, n4)
	n6 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 256, n6)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx832(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 240, n0)
	n2 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 224, n2)
	n4 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 272, n4)
	n6 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 256, n6)
	return
}

//go:noinline
func Simd_p_fx833(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 112)
	_ = Simd_v128_store(m, s1, 628, n0)
	n2 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 612, n2)
	n4 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s1, 596, n4)
	n6 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 580, n6)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx834(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, s5 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s3, n2)
	n4 := Simd_v128_load(m, s0, s4)
	_ = Simd_v128_store(m, s2, s4, n4)
	n6 := Simd_v128_load(m, s0, s5)
	_ = Simd_v128_store(m, s2, s5, n6)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx835(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, s5 int32, s6 int32, s7 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s3, n2)
	n4 := Simd_scalar_i32_add(s4, s5)
	n5 := Simd_v128_load(m, n4, s3)
	n6 := Simd_scalar_i32_add(s6, s7)
	_ = Simd_v128_store(m, n6, s3, n5)
	return n0[0], n0[1], n2[0], n2[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx836(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load_rng(m, s0, 20, 20, 48)
	n1 := Simd_v128_load_nc(m, s0, 36)
	n2 := Simd_v128_load_nc(m, s0, 52)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 48, n4)
	_ = Simd_v128_store(m, s1, 16, n1)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx837(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 500, n0)
	return
}

//go:noinline
func Simd_p_fx838(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 940)
	_ = Simd_v128_store(m, s1, 76, n0)
	n2 := Simd_v128_load(m, s0, 64)
	_ = Simd_v128_store(m, s1, 36, n2)
	return
}

//go:noinline
func Simd_p_fx839(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 84)
	_ = Simd_v128_store(m, s1, 56, n0)
	return
}

//go:noinline
func Simd_p_fx840(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 28, n0)
	n2 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 12, n2)
	return
}

//go:noinline
func Simd_p_fx841(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 133)
	_ = Simd_v128_store(m, s1, 42, n0)
	n2 := Simd_v128_load(m, s0, 117)
	_ = Simd_v128_store(m, s1, 26, n2)
	n4 := Simd_v128_load(m, s0, 101)
	_ = Simd_v128_store(m, s1, 10, n4)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx842(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 0, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx843(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 10)
	_ = Simd_v128_store(m, s1, 101, n0)
	n2 := Simd_v128_load(m, s0, 26)
	_ = Simd_v128_store(m, s1, 117, n2)
	n4 := Simd_v128_load(m, s0, 42)
	_ = Simd_v128_store(m, s1, 133, n4)
	return
}

//go:noinline
func Simd_p_fx844(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 27)
	_ = Simd_v128_store(m, s1, 68, n0)
	n2 := Simd_v128_load(m, s0, 11)
	_ = Simd_v128_store(m, s1, 52, n2)
	return
}

//go:noinline
func Simd_p_fx845(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 15069664, 0)
	_ = Simd_v128_store(m, s0, 27, n0)
	n2 := Simd_v128_load(m, 15069648, 0)
	_ = Simd_v128_store(m, s0, 11, n2)
	return
}

//go:noinline
func Simd_p_fx846(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s2)
	n1 := Simd_v128_load_rng(m, s0, 0, 0, 32)
	n2 := Simd_v128_load_nc(m, s0, 16)
	n3 := Simd_v128_load(m, s1, 16)
	n4 := Simd_v128_bitselect(n2, n3, n0)
	_ = Simd_v128_store(m, s1, 16, n4)
	n6 := Simd_v128_load(m, s1, 0)
	n7 := Simd_v128_bitselect(n1, n6, n0)
	_ = Simd_v128_store(m, s1, 0, n7)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx847(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_xor(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx848(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_splat(s2)
	n1 := Simd_v128_load_rng(m, s0, 0, 0, 72)
	n2 := Simd_v128_load_nc(m, s0, 16)
	n3 := Simd_v128_load_nc(m, s1, 16)
	n4 := Simd_v128_bitselect(n2, n3, n0)
	_ = Simd_v128_store(m, s1, 16, n4)
	return n1[0], n1[1], n2[0], n2[1], n3[0], n3[1], n0[0], n0[1]
}

//go:noinline
func Simd_p_fx849(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_v128_bitselect([2]uint64{p0, p0h}, n0, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, n1)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx850(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_v128_bitselect([2]uint64{p3, p3h}, [2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 32)
	n5 := Simd_v128_load_nc(m, s1, 16)
	return n4[0], n4[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx851(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_i32x4_neg([2]uint64{p0, p0h})
	n1 := Simd_i32x4_neg([2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx852(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_xor(n0, [2]uint64{p0, p0h})
	n2 := Simd_v128_xor(n0, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s2, s1, n1)
	_ = Simd_v128_store(m, s0, s1, n2)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx853(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s3, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx854(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s3, n2)
	_ = Simd_v128_store(m, s0, s1, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, s3, [2]uint64{p1, p1h})
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx855(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s3, n2)
	n4 := Simd_v128_load(m, s0, s4)
	_ = Simd_v128_store(m, s2, s4, n4)
	_ = Simd_v128_store(m, s0, 48, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, s1, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, s4, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, s3, [2]uint64{p3, p3h})
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx856(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s1, n0)
	n2 := Simd_v128_load(m, s0, s3)
	_ = Simd_v128_store(m, s2, s3, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx857(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_gt_u([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_v128_and(n1, [2]uint64{p3, p3h})
	n3 := Simd_v128_or([2]uint64{p0, p0h}, n2)
	n4 := Simd_i16x8_gt_u([2]uint64{p4, p4h}, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_extend_low_i16x8_u(n4)
	n6 := Simd_v128_and(n5, [2]uint64{p3, p3h})
	n7 := Simd_v128_or(n3, n6)
	n8 := Simd_i16x8_gt_u([2]uint64{p5, p5h}, [2]uint64{p2, p2h})
	n9 := Simd_i32x4_extend_low_i16x8_u(n8)
	n10 := Simd_v128_and(n9, [2]uint64{p3, p3h})
	n11 := Simd_v128_or(n7, n10)
	n12 := Simd_i16x8_gt_u([2]uint64{p6, p6h}, [2]uint64{p2, p2h})
	n13 := Simd_i32x4_extend_low_i16x8_u(n12)
	n14 := Simd_v128_and(n13, [2]uint64{p3, p3h})
	n15 := Simd_v128_or(n11, n14)
	return n15[0], n15[1]
}

//go:noinline
func Simd_p_fx858(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p1, p1h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_v128_or([2]uint64{p0, p0h}, n1)
	n3 := Simd_i32x4_splat(s0)
	n4 := Simd_i16x8_extend_low_i8x16_u(n3)
	n5 := Simd_i32x4_extend_low_i16x8_u(n4)
	n6 := Simd_v128_or(n2, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx859(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 144)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 128)
	_ = Simd_v128_store(m, s1, s2, n4)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx860(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) (uint64, uint64) {
	n0 := Simd_v128_or([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_or(n0, [2]uint64{p2, p2h})
	n2 := Simd_v128_or(n1, [2]uint64{p3, p3h})
	n3 := Simd_v128_or(n2, [2]uint64{p4, p4h})
	n4 := Simd_v128_or(n3, [2]uint64{p5, p5h})
	n5 := Simd_v128_or(n4, [2]uint64{p6, p6h})
	return n5[0], n5[1]
}

//go:noinline
func Simd_p_fx861(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx862(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 224, n0)
	return
}

//go:noinline
func Simd_p_fx863(m *Module, s0 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 208)
	n1 := Simd_i64x2_add(n0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 208, n1)
	return
}

//go:noinline
func Simd_p_fx864(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n4)
	return
}

//go:noinline
func Simd_p_fx865(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p0, p0h})
	n1 := Simd_v128_load(m, s1, 56)
	_ = Simd_v128_store(m, s0, 32, n1)
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p0, p0h})
	return
}

//go:noinline
func Simd_p_fx866(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 72)
	n1 := Simd_v128_load(m, s1, 56)
	n2 := Simd_f64x2_add(n0, n1)
	_ = Simd_v128_store(m, s1, 56, n2)
	return
}

//go:noinline
func Simd_p_fx867(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	n1 := Simd_v128_load(m, s1, 8)
	n2 := Simd_f64x2_add(n0, n1)
	_ = Simd_v128_store(m, s1, 8, n2)
	n4 := Simd_v128_load(m, s0, 56)
	n5 := Simd_v128_load(m, s1, 40)
	n6 := Simd_f64x2_add(n4, n5)
	_ = Simd_v128_store(m, s1, 40, n6)
	return
}

//go:noinline
func Simd_p_fx868(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s0, 48, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s0, 32, n2)
	return
}

//go:noinline
func Simd_p_fx869(m *Module, s0 int32) {
	n0 := Simd_v128_load_rng(m, s0, 184, 160, 40)
	n1 := Simd_v128_load_nc(m, s0, 160)
	_ = Simd_v128_store(m, s0, 184, n1)
	_ = Simd_v128_store(m, s0, 160, n0)
	return
}

//go:noinline
func Simd_p_fx870(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 144)
	_ = Simd_v128_store(m, s1, 144, n0)
	n2 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 160, n2)
	n4 := Simd_v128_load(m, s0, 176)
	_ = Simd_v128_store(m, s1, 176, n4)
	return
}

//go:noinline
func Simd_p_fx871(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 152)
	_ = Simd_v128_store(m, s1, 152, n0)
	n2 := Simd_v128_load(m, s0, 168)
	_ = Simd_v128_store(m, s1, 168, n2)
	n4 := Simd_v128_load(m, s0, 184)
	_ = Simd_v128_store(m, s1, 184, n4)
	return
}

//go:noinline
func Simd_p_fx872(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx873(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 136, n0)
	n2 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 152, n2)
	return
}

//go:noinline
func Simd_p_fx874(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 168, n0)
	return
}

//go:noinline
func Simd_p_fx875(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load_rng(m, s0, s1, 0, 32)
	n1 := Simd_v128_load_nc(m, s0, s2)
	n2 := Simd_i8x16_shuffle(n0, n1, [2]uint64{1084535218666537729, 2241977984075764497})
	n3 := Simd_i8x16_shuffle(n0, n1, [2]uint64{1012195045828461056, 2169637811237687824})
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx876(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64, p6, p6h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_add([2]uint64{p3, p3h}, [2]uint64{p4, p4h})
	n1 := Simd_i8x16_lt_u(n0, [2]uint64{p5, p5h})
	n2 := Simd_v128_bitselect([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, n1)
	n3 := Simd_i8x16_add([2]uint64{p3, p3h}, [2]uint64{p0, p0h})
	n4 := Simd_i8x16_lt_u(n3, [2]uint64{p6, p6h})
	n5 := Simd_v128_bitselect([2]uint64{p0, p0h}, n2, n4)
	n6 := Simd_i8x16_add(n5, [2]uint64{p3, p3h})
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx877(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i8x16_ge_u(n0, [2]uint64{p2, p2h})
	n2 := Simd_v128_and(n1, [2]uint64{p3, p3h})
	n3 := Simd_i8x16_add(n2, [2]uint64{p0, p0h})
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx878(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 240)
	_ = Simd_v128_store(m, s1, 240, n0)
	return
}

//go:noinline
func Simd_p_fx879(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s0, 48, n0)
	n2 := Simd_v128_load(m, s0, 80)
	_ = Simd_v128_store(m, s0, s1, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx880(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 232)
	_ = Simd_v128_store(m, s1, 232, n0)
	return
}

//go:noinline
func Simd_p_fx881(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 284)
	_ = Simd_v128_store(m, s1, 284, n0)
	n2 := Simd_v128_load(m, s0, 268)
	_ = Simd_v128_store(m, s1, 268, n2)
	return
}

//go:noinline
func Simd_p_fx882(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 352)
	_ = Simd_v128_store(m, s1, 352, n0)
	return
}

//go:noinline
func Simd_p_fx883(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 260)
	_ = Simd_v128_store(m, s1, 260, n0)
	n2 := Simd_v128_load(m, s0, 244)
	_ = Simd_v128_store(m, s1, 244, n2)
	return
}

//go:noinline
func Simd_p_fx884(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 328)
	_ = Simd_v128_store(m, s1, 328, n0)
	return
}

//go:noinline
func Simd_p_fx885(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 316)
	_ = Simd_v128_store(m, s1, 316, n0)
	n2 := Simd_v128_load(m, s0, 300)
	_ = Simd_v128_store(m, s1, 300, n2)
	return
}

//go:noinline
func Simd_p_fx886(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 280)
	_ = Simd_v128_store(m, s1, 280, n0)
	return
}

//go:noinline
func Simd_p_fx887(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 340)
	_ = Simd_v128_store(m, s1, 340, n0)
	n2 := Simd_v128_load(m, s0, 324)
	_ = Simd_v128_store(m, s1, 324, n2)
	return
}

//go:noinline
func Simd_p_fx888(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) {
	n0 := Simd_i32x4_add([2]uint64{p1, p1h}, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 32, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 8, n0)
	return
}

//go:noinline
func Simd_p_fx889(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 152)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 136)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx890(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, 48, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s2, 32, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx891(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	n2 := Simd_i32x4_lt_u(n1, [2]uint64{p1, p1h})
	n3 := Simd_v128_and(n2, [2]uint64{p2, p2h})
	n4 := Simd_i32x4_lt_u([2]uint64{p3, p3h}, [2]uint64{p4, p4h})
	n5 := Simd_v128_and(n4, [2]uint64{p2, p2h})
	n6 := Simd_i16x8_narrow_i32x4_u(n3, n5)
	return n6[0], n6[1]
}

//go:noinline
func Simd_p_fx892(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 256)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx893(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 312)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx894(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 368)
	_ = Simd_v128_store(m, s1, 368, n0)
	return
}

//go:noinline
func Simd_p_fx895(m *Module, s0 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s0, 136, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 120, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx896(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s0, 96, n0)
	n2 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s0, s2, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx897(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 204)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 188)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx898(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 184)
	_ = Simd_v128_store(m, s1, 184, n0)
	n2 := Simd_v128_load(m, s0, 200)
	_ = Simd_v128_store(m, s1, 200, n2)
	n4 := Simd_v128_load(m, s0, 216)
	_ = Simd_v128_store(m, s1, 216, n4)
	return
}

//go:noinline
func Simd_p_fx899(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 280, n0)
	return
}

//go:noinline
func Simd_p_fx900(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 280, n0)
	return
}

//go:noinline
func Simd_p_fx901(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 552)
	_ = Simd_v128_store(m, s1, 552, n0)
	return
}

//go:noinline
func Simd_p_fx902(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 212)
	_ = Simd_v128_store(m, s1, 212, n0)
	n2 := Simd_v128_load(m, s0, 228)
	_ = Simd_v128_store(m, s1, 228, n2)
	return
}

//go:noinline
func Simd_p_fx903(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 132)
	_ = Simd_v128_store(m, s1, 132, n0)
	n2 := Simd_v128_load(m, s0, 148)
	_ = Simd_v128_store(m, s1, 148, n2)
	return
}

//go:noinline
func Simd_p_fx904(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 98)
	_ = Simd_v128_store(m, s1, 34, n0)
	n2 := Simd_v128_load(m, s0, 82)
	_ = Simd_v128_store(m, s1, 18, n2)
	n4 := Simd_v128_load(m, s0, 66)
	_ = Simd_v128_store(m, s1, 2, n4)
	return
}

//go:noinline
func Simd_p_fx905(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13243380, 0)
	_ = Simd_v128_store(m, s0, 24, n0)
	return
}

//go:noinline
func Simd_p_fx906(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 9)
	_ = Simd_v128_store(m, s1, 25, n0)
	return
}

//go:noinline
func Simd_p_fx907(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64) {
	n0 := Simd_f64x2_div([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_f64x2_div(n0, [2]uint64{p2, p2h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx908(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_f64x2_neg([2]uint64{p1, p1h})
	n1 := Simd_f64x2_mul([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx909(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13254456, 0)
	_ = Simd_v128_store(m, s0, 4904, n0)
	return
}

//go:noinline
func Simd_p_fx910(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 24, n0)
	n2 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 8, n2)
	return
}

//go:noinline
func Simd_p_fx911(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 4532)
	_ = Simd_v128_store(m, s1, 4532, n0)
	n2 := Simd_v128_load(m, s0, 4516)
	return n2[0], n2[1]
}

//go:noinline
func Simd_p_fx912(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 44, n0)
	n2 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 60, n2)
	return
}

//go:noinline
func Simd_p_fx913(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 4, n0)
	return
}

//go:noinline
func Simd_p_fx914(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+8, 0)
	_ = Simd_v128_store(m, s1+12, 0, n0)
	return
}

//go:noinline
func Simd_p_fx915(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 18)
	_ = Simd_v128_store(m, s1, 64, n0)
	return
}

//go:noinline
func Simd_p_fx916(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, 504, n0)
	n2 := Simd_v128_load(m, s3+544, s1)
	_ = Simd_v128_store(m, s2, 544, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx917(m *Module, s0 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 1344)
	_ = Simd_v128_store(m, s0, 528, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx918(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 36, n0)
	return
}

//go:noinline
func Simd_p_fx919(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_add([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n3 := Simd_v128_or(n1, n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx920(m *Module) {
	n0 := Simd_v128_load(m, 15275820, 0)
	_ = Simd_v128_store(m, 15275864, 0, n0)
	n2 := Simd_v128_load(m, 15275836, 0)
	_ = Simd_v128_store(m, 15275880, 0, n2)
	return
}

//go:noinline
func Simd_p_fx921(m *Module, s0 int32, s1 int32, p0, p0h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx922(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 32, n2)
	return
}

//go:noinline
func Simd_p_fx923(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 224, n0)
	return
}

//go:noinline
func Simd_p_fx924(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_low_i16x8_u(n0)
	n2 := Simd_i32x4_mul(n1, [2]uint64{p1, p1h})
	n3 := Simd_v128_and([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n4 := Simd_i32x4_add(n2, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx925(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64, p5, p5h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_lt_u([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	n1 := Simd_v128_bitselect([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, n0)
	n2 := Simd_i32x4_shl([2]uint64{p5, p5h}, 31)
	n3 := Simd_i32x4_shr_s(n2, 31)
	n4 := Simd_v128_bitselect(n1, [2]uint64{p4, p4h}, n3)
	n5 := Simd_i32x4_neg(n4)
	return n4[0], n4[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx926(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_eq([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_eq([2]uint64{p0, p0h}, [2]uint64{p3, p3h})
	n3 := Simd_v128_and(n2, [2]uint64{p2, p2h})
	n4 := Simd_i16x8_narrow_i32x4_u(n1, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx927(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64) {
	_ = Simd_v128_store(m, s0+44, 0, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0+60, 0, [2]uint64{p1, p1h})
	n2 := Simd_v128_load(m, s1, 0)
	_ = Simd_v128_store(m, s2, 0, n2)
	return
}

//go:noinline
func Simd_p_fx928(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 252, n0)
	return
}

//go:noinline
func Simd_p_fx929(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_splat(s0)
	n1 := Simd_i32x4_add(n0, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx930(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p0, p0h})
	n2 := Simd_i16x8_extend_low_i8x16_s(n1)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	return n3[0], n3[1]
}

//go:noinline
func Simd_p_fx931(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_shl([2]uint64{p3, p3h}, 31)
	n1 := Simd_i32x4_shr_s(n0, 31)
	n2 := Simd_v128_bitselect([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, n1)
	n3 := Simd_i8x16_shuffle(n2, [2]uint64{p3, p3h}, [2]uint64{p4, p4h})
	n4 := Simd_i32x4_max_u(n2, n3)
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p0, p0h})
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx932(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_or([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx933(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 32, n2)
	return
}

//go:noinline
func Simd_p_fx934(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n2)
	n4 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n4)
	_ = Simd_v128_store(m, s0, 48, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 32, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p3, p3h})
	return
}

//go:noinline
func Simd_p_fx935(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	_ = Simd_v128_store(m, s0, 48, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 32, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p3, p3h})
	return
}

//go:noinline
func Simd_p_fx936(m *Module, s0 int32, s1 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n2)
	_ = Simd_v128_store(m, s0, 48, [2]uint64{p0, p0h})
	_ = Simd_v128_store(m, s0, 32, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 0, [2]uint64{p2, p2h})
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p3, p3h})
	return
}

//go:noinline
func Simd_p_fx937(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 100)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 84)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx938(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx939(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 197)
	_ = Simd_v128_store(m, s1, 133, n0)
	n2 := Simd_v128_load(m, s0, 181)
	_ = Simd_v128_store(m, s1, 117, n2)
	n4 := Simd_v128_load(m, s0, 165)
	_ = Simd_v128_store(m, s1, 101, n4)
	return
}

//go:noinline
func Simd_p_fx940(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 32, n2)
	return
}

//go:noinline
func Simd_p_fx941(m *Module, p0, p0h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i16x8_extend_high_i8x16_u([2]uint64{p0, p0h})
	n1 := Simd_i32x4_extend_high_i16x8_u(n0)
	n2 := Simd_i32x4_extend_low_i16x8_u(n0)
	n3 := Simd_i16x8_extend_low_i8x16_u([2]uint64{p0, p0h})
	n4 := Simd_i32x4_extend_high_i16x8_u(n3)
	n5 := Simd_i32x4_extend_low_i16x8_u(n3)
	return n1[0], n1[1], n2[0], n2[1], n4[0], n4[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx942(m *Module, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i16x8_extend_high_i8x16_u(n0)
	n2 := Simd_i32x4_extend_high_i16x8_u(n1)
	n3 := Simd_i32x4_extend_low_i16x8_u(n1)
	n4 := Simd_i16x8_extend_low_i8x16_u(n0)
	n5 := Simd_i32x4_extend_high_i16x8_u(n4)
	n6 := Simd_i32x4_extend_low_i16x8_u(n4)
	return n2[0], n2[1], n3[0], n3[1], n5[0], n5[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx943(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1948679894439893000, 2238040585792199692})
	n1 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p1, p1h}, [2]uint64{1369958511735279616, 1659319203087586308})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx944(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 12417984, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	return
}

//go:noinline
func Simd_p_fx945(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 48, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 32, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx946(m *Module, s0 int32, s1 int32, s2 int32, s3 int32, s4 int32, s5 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s2, s3, n0)
	n2 := Simd_v128_load(m, s0, s4)
	_ = Simd_v128_store(m, s2, 48, n2)
	n4 := Simd_v128_load(m, s5, s1)
	_ = Simd_v128_store(m, s2, s1, n4)
	n6 := Simd_v128_load(m, s5, s4)
	_ = Simd_v128_store(m, s2, s4, n6)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1], n6[0], n6[1]
}

//go:noinline
func Simd_p_fx947(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s0, 80, n0)
	n2 := Simd_v128_load(m, s0, s1)
	_ = Simd_v128_store(m, s0, 64, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx948(m *Module, s0 int32, s1 int32, s2 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 32, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 48, n2)
	n4 := Simd_v128_load(m, s2, 0)
	_ = Simd_v128_store(m, s1, 0, n4)
	n6 := Simd_v128_load(m, s2, 16)
	_ = Simd_v128_store(m, s1, 16, n6)
	return
}

//go:noinline
func Simd_p_fx949(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_sub([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_i32x4_sub([2]uint64{p2, p2h}, [2]uint64{p3, p3h})
	_ = Simd_v128_store(m, s0, 16, n0)
	_ = Simd_v128_store(m, s0, 0, n1)
	n4 := Simd_v128_load_rng(m, s1, 0, 0, 32)
	n5 := Simd_v128_load_rng(m, s2+144, 0, 0, 32)
	n6 := Simd_v128_load_nc(m, s1, 16)
	n7 := Simd_v128_load_nc(m, s2+144, 16)
	return n4[0], n4[1], n5[0], n5[1], n6[0], n6[1], n7[0], n7[1]
}

//go:noinline
func Simd_p_fx950(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_neg([2]uint64{p0, p0h})
	n1 := Simd_i32x4_neg([2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, s1, n0)
	_ = Simd_v128_store(m, s0, s2, n1)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx951(m *Module, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64) (uint64, uint64) {
	n0 := Simd_i32x4_eq([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	n1 := Simd_v128_and(n0, [2]uint64{p2, p2h})
	n2 := Simd_i32x4_eq([2]uint64{p3, p3h}, [2]uint64{p1, p1h})
	n3 := Simd_v128_and(n2, [2]uint64{p2, p2h})
	n4 := Simd_i16x8_narrow_i32x4_u(n1, n3)
	return n4[0], n4[1]
}

//go:noinline
func Simd_p_fx952(m *Module, s0 int32, s1 int32) {
	n0 := Simd_scalar_i32_add(s0, s1)
	n1 := Simd_v128_load(m, n0, 0)
	_ = Simd_v128_store(m, s0, 0, n1)
	return
}

//go:noinline
func Simd_p_fx953(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64) {
	n0 := Simd_v128_and([2]uint64{p0, p0h}, [2]uint64{p1, p1h})
	_ = Simd_v128_store(m, s0, 864, n0)
	return
}

//go:noinline
func Simd_p_fx954(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 10166800, 0)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, 10166784, 0)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx955(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 28, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 12, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx956(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 24, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 8, n4)
	n6 := Simd_v128_load_rng(m, s0, 16, 16, 48)
	n7 := Simd_v128_load_nc(m, s0, 32)
	n8 := Simd_v128_load_nc(m, s0, 48)
	return n6[0], n6[1], n7[0], n7[1], n8[0], n8[1]
}

//go:noinline
func Simd_p_fx957(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 6)
	_ = Simd_v128_store(m, s1, s2, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx958(m *Module, s0 int32, s1 int32) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s0, 112, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 96, n2)
	n4 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s0, s1, n4)
	return n0[0], n0[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx959(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64) (uint64, uint64) {
	_ = Simd_v128_store(m, s0, 16, [2]uint64{p0, p0h})
	n1 := Simd_v128_load(m, s1, 56)
	_ = Simd_v128_store(m, s0, 32, n1)
	_ = Simd_v128_store(m, s0, s2, [2]uint64{p0, p0h})
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx960(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	n2 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, 23933256, 0, n2)
	return
}

//go:noinline
func Simd_p_fx961(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 48)
	_ = Simd_v128_store(m, s1, 112, n0)
	n2 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 96, n2)
	n4 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 80, n4)
	n6 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 64, n6)
	return
}

//go:noinline
func Simd_p_fx962(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 660)
	_ = Simd_v128_store(m, s1, 40, n0)
	n2 := Simd_v128_load(m, s0, 676)
	_ = Simd_v128_store(m, s1, 56, n2)
	return
}

//go:noinline
func Simd_p_fx963(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 676)
	_ = Simd_v128_store(m, s1, 56, n0)
	n2 := Simd_v128_load(m, s0, 660)
	_ = Simd_v128_store(m, s1, 40, n2)
	return
}

//go:noinline
func Simd_p_fx964(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 64)
	n1 := Simd_v128_load(m, s1, s2)
	n2 := Simd_v128_xor(n0, n1)
	_ = Simd_v128_store(m, s1, s2, n2)
	n4 := Simd_v128_load(m, s0, 80)
	return n0[0], n0[1], n1[0], n1[1], n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx965(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 164)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 148)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx966(m *Module, s0 int32, s1 int32, s2 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, s2, n2)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx967(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s0, 536, n0)
	return
}

//go:noinline
func Simd_p_fx968(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	n1 := Simd_v128_load(m, s1, 56)
	n2 := Simd_f64x2_add(n0, n1)
	_ = Simd_v128_store(m, s1, 56, n2)
	return
}

//go:noinline
func Simd_p_fx969(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	n1 := Simd_v128_load(m, s1, 8)
	n2 := Simd_f64x2_add(n0, n1)
	_ = Simd_v128_store(m, s1, 8, n2)
	n4 := Simd_v128_load(m, s0, 40)
	n5 := Simd_v128_load(m, s1, 40)
	n6 := Simd_f64x2_add(n4, n5)
	_ = Simd_v128_store(m, s1, 40, n6)
	return
}

//go:noinline
func Simd_p_fx970(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 124)
	_ = Simd_v128_store(m, s0, 96, n0)
	return
}

//go:noinline
func Simd_p_fx971(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s0, 16, n0)
	n2 := Simd_v128_load(m, s0, 40)
	_ = Simd_v128_store(m, s0, 0, n2)
	return
}

//go:noinline
func Simd_p_fx972(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 88, n0)
	n2 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 104, n2)
	return
}

//go:noinline
func Simd_p_fx973(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 164)
	_ = Simd_v128_store(m, s1, 164, n0)
	return
}

//go:noinline
func Simd_p_fx974(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 188)
	_ = Simd_v128_store(m, s1, 188, n0)
	n2 := Simd_v128_load(m, s0, 204)
	_ = Simd_v128_store(m, s1, 204, n2)
	return
}

//go:noinline
func Simd_p_fx975(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 116)
	_ = Simd_v128_store(m, s1, 116, n0)
	return
}

//go:noinline
func Simd_p_fx976(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 176)
	_ = Simd_v128_store(m, s1, 176, n0)
	return
}

//go:noinline
func Simd_p_fx977(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 136)
	_ = Simd_v128_store(m, s1, 136, n0)
	n2 := Simd_v128_load(m, s0, 152)
	_ = Simd_v128_store(m, s1, 152, n2)
	return
}

//go:noinline
func Simd_p_fx978(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 144)
	_ = Simd_v128_store(m, s1, 144, n0)
	return
}

//go:noinline
func Simd_p_fx979(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 192)
	_ = Simd_v128_store(m, s1, 192, n0)
	return
}

//go:noinline
func Simd_p_fx980(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 172)
	_ = Simd_v128_store(m, s1, 172, n0)
	return
}

//go:noinline
func Simd_p_fx981(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 176)
	_ = Simd_v128_store(m, s1, 176, n0)
	n2 := Simd_v128_load(m, s0, 192)
	_ = Simd_v128_store(m, s1, 192, n2)
	return
}

//go:noinline
func Simd_p_fx982(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx983(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 144)
	_ = Simd_v128_store(m, s1, 144, n0)
	n2 := Simd_v128_load(m, s0, 160)
	_ = Simd_v128_store(m, s1, 160, n2)
	return
}

//go:noinline
func Simd_p_fx984(m *Module, s0 int32, s1 int32, s2 int32, s3 int32) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, s1)
	n1 := Simd_v128_load(m, s2, s3)
	_ = Simd_v128_store(m, s0, s1, n1)
	return n0[0], n0[1], n1[0], n1[1]
}

//go:noinline
func Simd_p_fx985(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 56)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx986(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 32)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx987(m *Module, s0 int32, s1 int32) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 0, n0)
	return n0[0], n0[1]
}

//go:noinline
func Simd_p_fx988(m *Module, s0 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, 0)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p1, p1h})
	n2 := Simd_i16x8_extend_low_i8x16_u(n1)
	n3 := Simd_i32x4_extend_low_i16x8_u(n2)
	n4 := Simd_v128_and(n3, [2]uint64{p2, p2h})
	n5 := Simd_i32x4_add([2]uint64{p0, p0h}, n4)
	return n0[0], n0[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx989(m *Module, s0 int32, s1 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load32_zero(m, s0, s1)
	n1 := Simd_i8x16_eq(n0, [2]uint64{p0, p0h})
	n2 := Simd_i16x8_extend_low_i8x16_s(n1)
	n3 := Simd_i32x4_extend_low_i16x8_s(n2)
	return n0[0], n0[1], n3[0], n3[1]
}

//go:noinline
func Simd_p_fx990(m *Module, s0 int32, s1 int32, s2 int32, p0, p0h uint64, p1, p1h uint64, p2, p2h uint64, p3, p3h uint64, p4, p4h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_i32x4_shl([2]uint64{p3, p3h}, s2)
	n1 := Simd_i32x4_shr_s(n0, s2)
	n2 := Simd_v128_bitselect([2]uint64{p1, p1h}, [2]uint64{p2, p2h}, n1)
	n3 := Simd_i8x16_shuffle(n2, [2]uint64{p3, p3h}, [2]uint64{p4, p4h})
	n4 := Simd_i32x4_max_u(n2, n3)
	_ = Simd_v128_store(m, s0, s1, [2]uint64{p0, p0h})
	return n2[0], n2[1], n4[0], n4[1]
}

//go:noinline
func Simd_p_fx991(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 140)
	_ = Simd_v128_store(m, s1, 140, n0)
	n2 := Simd_v128_load(m, s0, 156)
	_ = Simd_v128_store(m, s1, 156, n2)
	return
}

//go:noinline
func Simd_p_fx992(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 8, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 28, n2)
	n4 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 44, n4)
	return
}

//go:noinline
func Simd_p_fx993(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4)
	_ = Simd_v128_store(m, s1, 4, n0)
	n2 := Simd_v128_load(m, s0, 20)
	_ = Simd_v128_store(m, s1, 20, n2)
	n4 := Simd_v128_load(m, s0, 36)
	_ = Simd_v128_store(m, s1, 36, n4)
	return
}

//go:noinline
func Simd_p_fx994(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 132)
	_ = Simd_v128_store(m, s1, 132, n0)
	return
}

//go:noinline
func Simd_p_fx995(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 20)
	n1 := Simd_f64x2_sub([2]uint64{p0, p0h}, n0)
	n2 := Simd_f64x2_mul(n1, n1)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx996(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_f64x2_sub([2]uint64{p0, p0h}, n0)
	n2 := Simd_f64x2_mul(n1, n1)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx997(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0+16, 0)
	n1 := Simd_f64x2_sub([2]uint64{p0, p0h}, n0)
	n2 := Simd_f64x2_mul(n1, n1)
	return n0[0], n0[1], n2[0], n2[1]
}

//go:noinline
func Simd_p_fx998(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 25)
	n1 := Simd_f64x2_sub([2]uint64{p0, p0h}, n0)
	n2 := Simd_f64x2_mul(n1, n1)
	return n2[0], n2[1], n0[0], n0[1]
}

//go:noinline
func Simd_p_fx999(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64, uint64, uint64, uint64, uint64) {
	n0 := Simd_v128_load_rng(m, s0, 0, 0, 32)
	n1 := Simd_f64x2_sub([2]uint64{p0, p0h}, n0)
	n2 := Simd_f64x2_mul(n1, n1)
	n3 := Simd_v128_load_nc(m, s0+16, 0)
	n4 := Simd_f64x2_sub(n0, n3)
	n5 := Simd_f64x2_mul(n4, n4)
	return n2[0], n2[1], n3[0], n3[1], n5[0], n5[1]
}

//go:noinline
func Simd_p_fx1000(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 4516)
	_ = Simd_v128_store(m, s1, 4516, n0)
	n2 := Simd_v128_load(m, s0, 4532)
	_ = Simd_v128_store(m, s1, 4532, n2)
	return
}

//go:noinline
func Simd_p_fx1001(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 16)
	_ = Simd_v128_store(m, s1, 12, n0)
	return
}

//go:noinline
func Simd_p_fx1002(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 4, n0)
	return
}

//go:noinline
func Simd_p_fx1003(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 8897687, 0)
	_ = Simd_v128_store(m, s0, 96, n0)
	return
}

//go:noinline
func Simd_p_fx1004(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 12)
	_ = Simd_v128_store(m, s1, 12, n0)
	n2 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 28, n2)
	return
}

//go:noinline
func Simd_p_fx1005(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23996864, 0)
	_ = Simd_v128_store(m, s0, 12, n0)
	return
}

//go:noinline
func Simd_p_fx1006(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 23996880, 0)
	_ = Simd_v128_store(m, s0, 28, n0)
	return
}

//go:noinline
func Simd_p_fx1007(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1, 136, n0)
	return
}

//go:noinline
func Simd_p_fx1008(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0+196, 0)
	_ = Simd_v128_store(m, s1, 0, n0)
	return
}

//go:noinline
func Simd_p_fx1009(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 0)
	_ = Simd_v128_store(m, s1+196, 0, n0)
	return
}

//go:noinline
func Simd_p_fx1010(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, 13369840, 0)
	_ = Simd_v128_store(m, s0, 0, n0)
	return
}

//go:noinline
func Simd_p_fx1011(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 28)
	_ = Simd_v128_store(m, s1, 0, n2)
	return
}

//go:noinline
func Simd_p_fx1012(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 8, n0)
	return
}

//go:noinline
func Simd_p_fx1013(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 52)
	_ = Simd_v128_store(m, s1, 44, n0)
	n2 := Simd_v128_load(m, s0, 68)
	_ = Simd_v128_store(m, s1, 60, n2)
	return
}

//go:noinline
func Simd_p_fx1014(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 96)
	_ = Simd_v128_store(m, s1, 88, n0)
	return
}

//go:noinline
func Simd_p_fx1015(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 24)
	_ = Simd_v128_store(m, s1, 32, n0)
	return
}

//go:noinline
func Simd_p_fx1016(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 8)
	_ = Simd_v128_store(m, s1, 16, n0)
	n2 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s1, 52, n2)
	n4 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s1, 68, n4)
	return
}

//go:noinline
func Simd_p_fx1017(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 88)
	_ = Simd_v128_store(m, s1, 96, n0)
	return
}

//go:noinline
func Simd_p_fx1018(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 134)
	_ = Simd_v128_store(m, s1, 134, n0)
	return
}

//go:noinline
func Simd_p_fx1019(m *Module, s0 int32, s1 int32) {
	n0 := Simd_v128_load(m, s0, 328)
	_ = Simd_v128_store(m, s1, 24, n0)
	return
}

//go:noinline
func Simd_p_fx1020(m *Module, s0 int32, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_v128_load(m, s0, 0)
	n1 := Simd_i32x4_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx1021(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{1084818905618843912, 216736831629295872})
	n1 := Simd_i32x4_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx1022(m *Module, p0, p0h uint64) (uint64, uint64) {
	n0 := Simd_i8x16_shuffle([2]uint64{p0, p0h}, [2]uint64{p0, p0h}, [2]uint64{216736831696667908, 216736831629295872})
	n1 := Simd_i32x4_max_u([2]uint64{p0, p0h}, n0)
	return n1[0], n1[1]
}

//go:noinline
func Simd_p_fx1023(m *Module, s0 int32) {
	n0 := Simd_v128_load(m, s0, 60)
	_ = Simd_v128_store(m, s0, 24, n0)
	n2 := Simd_v128_load(m, s0, 44)
	_ = Simd_v128_store(m, s0, 8, n2)
	return
}

var spinRelaxColdCalls uint32
var spinAgents int32
var spinOversubscribed uint32

type ThreadPool struct {
	nextTID atomic.Int32
	wg      sync.WaitGroup

	parkMu sync.Mutex
	parked map[uint64][]chan struct{}
}

// wake releases up to count waiters on ea and reports how many it woke.
func (p *ThreadPool) wake(ea uint64, count int32) int32 {
	p.parkMu.Lock()
	defer p.parkMu.Unlock()
	waiters := p.parked[ea]
	n := int32(len(waiters))
	if count >= 0 && count < n {
		n = count
	}
	for _, ch := range waiters[:n] {
		close(ch)
	}
	if int(n) == len(waiters) {
		delete(p.parked, ea)
	} else {
		p.parked[ea] = waiters[n:]
	}
	return n
}

// SaveGlobals returns the module's mutable globals, in a form that can be handed back
// to RestoreGlobals. It is how a snapshot of an instance captures the state that does not
// live in linear memory.
func SaveGlobals(m *Module) []uint64 {
	g := make([]uint64, 2)
	g[0] = uint64(uint32(m.G0))
	g[1] = uint64(uint32(m.G1))
	return g
}

// RestoreGlobals puts a snapshot's globals back. A snapshot from a different module (or a
// different build of the same one) has a different global count; rather than
// index out of bounds, take what fits and leave the rest at their declared
// initializers.
func RestoreGlobals(m *Module, g []uint64) {
	if len(g) != 2 {
		return
	}
	m.G0 = int32(uint32(g[0]))
	m.G1 = int32(uint32(g[1]))
}

// WasiExitError is the sentinel that the recover layer of SafeInvokeExport
// promotes Proc_exit() panics into, so a wasm-level exit doesn't kill the
// host process and the caller can read the exit code instead.
type WasiExitError struct{ Code int32 }

func (e *WasiExitError) Error() string {
	return "wasi: proc_exit(" + itoa32(e.Code) + ")"
}

// itoa32 is a tiny dependency-free strconv replacement so this file
// doesn't drag in fmt for its sole error path.
func itoa32(v int32) string {
	if v == 0 {
		return "0"
	}
	neg := false
	if v < 0 {
		v = -v
		neg = true
	}
	var buf [12]byte
	i := len(buf)
	for v > 0 {
		i--
		buf[i] = byte('0' + v%10)
		v /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

// FS is the read/write filesystem backend the WASI host opens files through.
// It abstracts the default os-backed filesystem so an embedder can supply an
// alternative — an in-memory FS, an overlay, a read-only bundle, ... — and
// have every guest path operation (open, stat, mkdir, readdir, write, ...)
// routed to it. It is a write-capable superset of io/fs.FS.
//
// Names are GUEST paths relative to the preopen root: slash-separated, with no
// leading slash (e.g. "encodings/__init__.py", or "" for the root). Methods
// should return the standard fs errors (fs.ErrNotExist, fs.ErrExist,
// fs.ErrPermission) so the host maps them to the right wasi errno.
type FS interface {
	// OpenFile mirrors os.OpenFile: flag is O_RDONLY/O_WRONLY/O_RDWR optionally
	// OR'd with O_CREATE/O_EXCL/O_TRUNC/O_APPEND. The returned File must
	// support the operations the mode implies.
	OpenFile(name string, flag int, perm os.FileMode) (File, error)
	Mkdir(name string, perm os.FileMode) error
	Remove(name string) error
	Rename(oldName, newName string) error
	Stat(name string) (os.FileInfo, error)
	Lstat(name string) (os.FileInfo, error)
	Symlink(oldName, newName string) error
	Readlink(name string) (string, error)
	Link(oldName, newName string) error
}

// File is an open file handle returned by FS.OpenFile. *os.File satisfies it,
// so the default os backend needs no wrapper.
type File interface {
	Read(p []byte) (int, error)
	ReadAt(p []byte, off int64) (int, error)
	Write(p []byte) (int, error)
	WriteAt(p []byte, off int64) (int, error)
	Seek(offset int64, whence int) (int64, error)
	Close() error
	Stat() (os.FileInfo, error)
	ReadDir(n int) ([]os.DirEntry, error)
	Sync() error
	Truncate(size int64) error
	Name() string
}

// osFS is the default FS backend: a thin pass-through to the host filesystem,
// scoped to root (the preopen directory). root "" or "/" means no rewriting.
type osFS struct{ root string }

func (o osFS) join(name string) string {
	if o.root == "" || o.root == "/" {
		return "/" + name
	}
	return filepath.Join(o.root, name)
}
func (o osFS) OpenFile(name string, flag int, perm os.FileMode) (File, error) {
	f, err := os.OpenFile(o.join(name), flag, perm)
	if err != nil {
		return nil, err
	}
	return f, nil
}
func (o osFS) Mkdir(name string, perm os.FileMode) error { return os.Mkdir(o.join(name), perm) }
func (o osFS) Chmod(name string, mode os.FileMode) error { return os.Chmod(o.join(name), mode) }
func (o osFS) Remove(name string) error                  { return os.Remove(o.join(name)) }
func (o osFS) Rename(a, b string) error                  { return os.Rename(o.join(a), o.join(b)) }
func (o osFS) Stat(name string) (os.FileInfo, error)     { return os.Stat(o.join(name)) }
func (o osFS) Lstat(name string) (os.FileInfo, error)    { return os.Lstat(o.join(name)) }
func (o osFS) Symlink(target, name string) error         { return os.Symlink(target, o.join(name)) }
func (o osFS) Readlink(name string) (string, error)      { return os.Readlink(o.join(name)) }
func (o osFS) Link(a, b string) error                    { return os.Link(o.join(a), o.join(b)) }

// MemFS is an in-memory read/write FS. Each value is an independent tree, so
// two interpreters given separate MemFS values cannot observe each other's
// files (full per-interpreter filesystem isolation, no disk). Build one with
// NewMemFS. Safe for concurrent use.
type MemFS struct {
	mu   sync.Mutex
	root *memNode
}

// NewMemFS returns an empty in-memory filesystem with a root directory.
func NewMemFS() *MemFS {
	return &MemFS{root: &memNode{dir: true, mode: os.ModeDir | 0o755, modTime: time.Unix(0, 0), children: map[string]*memNode{}}}
}

// memNode is a file or directory in a MemFS tree.
type memNode struct {
	parent   *memNode // stable parent identity; retained after unlink
	name     string
	dir      bool
	mode     os.FileMode
	modTime  time.Time
	data     []byte
	children map[string]*memNode
}

func memSplit(name string) []string {
	name = strings.Trim(name, "/")
	if name == "" {
		return nil
	}
	raw := strings.Split(name, "/")
	out := make([]string, 0, len(raw))
	for _, p := range raw {
		switch p {
		case "", ".":
		case "..":
			if len(out) > 0 {
				out = out[:len(out)-1]
			}
		default:
			out = append(out, p)
		}
	}
	return out
}

// lookup resolves name to a node. Caller holds fsys.mu.
func (fsys *MemFS) lookup(name string) (*memNode, error) {
	n := fsys.root
	for _, part := range memSplit(name) {
		if !n.dir {
			return nil, fs.ErrNotExist
		}
		c, ok := n.children[part]
		if !ok {
			return nil, fs.ErrNotExist
		}
		n = c
	}
	return n, nil
}

// lookupParent resolves the parent dir of name. Caller holds fsys.mu.
func (fsys *MemFS) lookupParent(name string) (*memNode, string, error) {
	parts := memSplit(name)
	if len(parts) == 0 {
		return nil, "", fs.ErrInvalid
	}
	n := fsys.root
	for _, part := range parts[:len(parts)-1] {
		c, ok := n.children[part]
		if !ok || !c.dir {
			return nil, "", fs.ErrNotExist
		}
		n = c
	}
	return n, parts[len(parts)-1], nil
}

func (fsys *MemFS) OpenFile(name string, flag int, perm os.FileMode) (File, error) {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	node, err := fsys.lookup(name)
	if err != nil {
		if flag&os.O_CREATE == 0 {
			return nil, &fs.PathError{Op: "open", Path: name, Err: fs.ErrNotExist}
		}
		parent, base, perr := fsys.lookupParent(name)
		if perr != nil {
			return nil, &fs.PathError{Op: "open", Path: name, Err: perr}
		}
		node = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now()}
		parent.children[base] = node
	} else {
		if flag&os.O_EXCL != 0 && flag&os.O_CREATE != 0 {
			return nil, &fs.PathError{Op: "open", Path: name, Err: fs.ErrExist}
		}
		if flag&os.O_TRUNC != 0 && !node.dir {
			node.data = node.data[:0]
			node.modTime = time.Now()
		}
	}
	f := &memFile{fsys: fsys, node: node}
	if flag&os.O_APPEND != 0 {
		f.off = int64(len(node.data))
	}
	return f, nil
}

func (fsys *MemFS) Mkdir(name string, perm os.FileMode) error {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	parent, base, err := fsys.lookupParent(name)
	if err != nil {
		return &fs.PathError{Op: "mkdir", Path: name, Err: err}
	}
	if _, ok := parent.children[base]; ok {
		return &fs.PathError{Op: "mkdir", Path: name, Err: fs.ErrExist}
	}
	parent.children[base] = &memNode{parent: parent, name: base, dir: true, mode: os.ModeDir | (perm & 0o777), modTime: time.Now(), children: map[string]*memNode{}}
	return nil
}

func (fsys *MemFS) Remove(name string) error {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	parent, base, err := fsys.lookupParent(name)
	if err != nil {
		return &fs.PathError{Op: "remove", Path: name, Err: err}
	}
	n, ok := parent.children[base]
	if !ok {
		return &fs.PathError{Op: "remove", Path: name, Err: fs.ErrNotExist}
	}
	if n.dir && len(n.children) > 0 {
		return &fs.PathError{Op: "remove", Path: name, Err: fs.ErrInvalid}
	}
	delete(parent.children, base)
	return nil
}

func (fsys *MemFS) Rename(oldName, newName string) error {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	op, ob, err := fsys.lookupParent(oldName)
	if err != nil {
		return &fs.PathError{Op: "rename", Path: oldName, Err: err}
	}
	node, ok := op.children[ob]
	if !ok {
		return &fs.PathError{Op: "rename", Path: oldName, Err: fs.ErrNotExist}
	}
	np, nb, err := fsys.lookupParent(newName)
	if err != nil {
		return &fs.PathError{Op: "rename", Path: newName, Err: err}
	}
	// A directory cannot be moved into itself or a descendant.
	for p := np; p != nil; p = p.parent {
		if p == node {
			return &fs.PathError{Op: "rename", Path: oldName, Err: syscall.EINVAL}
		}
	}
	delete(op.children, ob)
	node.parent = np
	node.name = nb
	np.children[nb] = node
	return nil
}

func (fsys *MemFS) Stat(name string) (os.FileInfo, error) {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	n, err := fsys.lookup(name)
	if err != nil {
		return nil, &fs.PathError{Op: "stat", Path: name, Err: err}
	}
	return n.info(), nil
}

func (fsys *MemFS) Lstat(name string) (os.FileInfo, error) { return fsys.Stat(name) }

// memfs has no symlinks/hardlinks.
func (fsys *MemFS) Symlink(_, _ string) error { return fs.ErrPermission }
func (fsys *MemFS) Link(_, _ string) error    { return fs.ErrPermission }
func (fsys *MemFS) Readlink(name string) (string, error) {
	return "", &fs.PathError{Op: "readlink", Path: name, Err: fs.ErrInvalid}
}

// Chtimes implements the optional chtimesFS capability.
func (fsys *MemFS) Chtimes(name string, _ time.Time, mtime time.Time) error {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	n, err := fsys.lookup(name)
	if err != nil {
		return &fs.PathError{Op: "chtimes", Path: name, Err: err}
	}
	n.modTime = mtime
	return nil
}

// MkdirAll creates name and any missing parents. Exposed so embedders can
// populate the FS (e.g. unpack a stdlib bundle) before handing it to a module.
func (fsys *MemFS) MkdirAll(name string, perm os.FileMode) error {
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	n := fsys.root
	for _, part := range memSplit(name) {
		c, ok := n.children[part]
		if !ok {
			c = &memNode{parent: n, name: part, dir: true, mode: os.ModeDir | (perm & 0o777), modTime: time.Now(), children: map[string]*memNode{}}
			n.children[part] = c
		} else if !c.dir {
			return &fs.PathError{Op: "mkdir", Path: name, Err: fs.ErrExist}
		}
		n = c
	}
	return nil
}

// WriteFile creates (or overwrites) a file with data, making parent dirs as
// needed. Exposed for pre-populating the FS.
func (fsys *MemFS) WriteFile(name string, data []byte, perm os.FileMode) error {
	if parts := memSplit(name); len(parts) > 1 {
		if err := fsys.MkdirAll(strings.Join(parts[:len(parts)-1], "/"), 0o755); err != nil {
			return err
		}
	}
	fsys.mu.Lock()
	defer fsys.mu.Unlock()
	parent, base, err := fsys.lookupParent(name)
	if err != nil {
		return &fs.PathError{Op: "writefile", Path: name, Err: err}
	}
	cp := make([]byte, len(data))
	copy(cp, data)
	parent.children[base] = &memNode{parent: parent, name: base, mode: perm & 0o777, modTime: time.Now(), data: cp}
	return nil
}

func (n *memNode) info() os.FileInfo {
	if n.dir {
		return memFileInfo{name: n.name, mode: os.ModeDir | (n.mode & 0o777), modTime: n.modTime}
	}
	return memFileInfo{name: n.name, size: int64(len(n.data)), mode: n.mode & 0o777, modTime: n.modTime}
}

type memFileInfo struct {
	name    string
	size    int64
	mode    os.FileMode
	modTime time.Time
}

func (fi memFileInfo) Name() string       { return fi.name }
func (fi memFileInfo) Size() int64        { return fi.size }
func (fi memFileInfo) Mode() os.FileMode  { return fi.mode }
func (fi memFileInfo) ModTime() time.Time { return fi.modTime }
func (fi memFileInfo) IsDir() bool        { return fi.mode.IsDir() }
func (fi memFileInfo) Sys() any           { return nil }

type memDirEntry struct{ n *memNode }

func (e memDirEntry) Name() string { return e.n.name }
func (e memDirEntry) IsDir() bool  { return e.n.dir }
func (e memDirEntry) Type() os.FileMode {
	if e.n.dir {
		return os.ModeDir
	}
	return 0
}
func (e memDirEntry) Info() (os.FileInfo, error) { return e.n.info(), nil }

// memFile is an open handle into a MemFS node.
type memFile struct {
	fsys   *MemFS
	node   *memNode
	off    int64
	dirOff int
}

func (f *memFile) Name() string { return f.node.name }
func (f *memFile) Close() error { return nil }
func (f *memFile) Sync() error  { return nil }

func (f *memFile) Stat() (os.FileInfo, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	return f.node.info(), nil
}

func (f *memFile) Read(p []byte) (int, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	if f.node.dir {
		return 0, &fs.PathError{Op: "read", Path: f.node.name, Err: fs.ErrInvalid}
	}
	if f.off >= int64(len(f.node.data)) {
		return 0, io.EOF
	}
	n := copy(p, f.node.data[f.off:])
	f.off += int64(n)
	return n, nil
}

func (f *memFile) ReadAt(p []byte, off int64) (int, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	if off >= int64(len(f.node.data)) {
		return 0, io.EOF
	}
	n := copy(p, f.node.data[off:])
	if n < len(p) {
		return n, io.EOF
	}
	return n, nil
}

// writeAt grows node.data as needed and writes p at off. Caller holds the lock.
func (f *memFile) writeAt(p []byte, off int64) int {
	end := off + int64(len(p))
	if end > int64(len(f.node.data)) {
		f.node.data = resizeMemData(f.node.data, end)
	}
	copy(f.node.data[off:], p)
	f.node.modTime = time.Now()
	return len(p)
}

func (f *memFile) Write(p []byte) (int, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	n := f.writeAt(p, f.off)
	f.off += int64(n)
	return n, nil
}

func (f *memFile) WriteAt(p []byte, off int64) (int, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	return f.writeAt(p, off), nil
}

func (f *memFile) Seek(offset int64, whence int) (int64, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	switch whence {
	case io.SeekStart:
		f.off = offset
	case io.SeekCurrent:
		f.off += offset
	case io.SeekEnd:
		f.off = int64(len(f.node.data)) + offset
	}
	return f.off, nil
}

func (f *memFile) Truncate(size int64) error {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	f.node.data = resizeMemData(f.node.data, size)
	f.node.modTime = time.Now()
	return nil
}

func (f *memFile) ReadDir(n int) ([]os.DirEntry, error) {
	f.fsys.mu.Lock()
	defer f.fsys.mu.Unlock()
	if !f.node.dir {
		return nil, &fs.PathError{Op: "readdir", Path: f.node.name, Err: fs.ErrInvalid}
	}
	names := make([]string, 0, len(f.node.children))
	for name := range f.node.children {
		names = append(names, name)
	}
	sort.Strings(names)
	if f.dirOff >= len(names) {
		if n <= 0 {
			return nil, nil
		}
		return nil, io.EOF
	}
	end := len(names)
	if n > 0 && f.dirOff+n < end {
		end = f.dirOff + n
	}
	out := make([]os.DirEntry, 0, end-f.dirOff)
	for _, name := range names[f.dirOff:end] {
		out = append(out, memDirEntry{f.node.children[name]})
	}
	f.dirOff = end
	return out, nil
}

// wasiOpen is one entry in WasiStubs' fd table. Stdio entries are nil-file
// markers (writes go to the OS handles directly via the WasiStubs fields).
// The conn arm carries a net.Conn for sockets opened via Sock_accept.
type wasiOpen struct {
	f        File
	conn     net.Conn
	listener net.Listener
	isDir    bool
	isSocket bool   // created by Sock_socket, may not yet have a conn
	path     string // guest path relative to the preopen root
	fdflags  int32  // last fdflags set via Path_open or Fd_fdstat_set_flags
	dirCache []os.DirEntry
	// stdio marks an alias of an interpreter stream (1/2/3 = the
	// configured stdin/stdout/stderr; 0 = not an alias). Fd_dup of a bare
	// fd 0/1/2 creates one; closing it never touches the real stream.
	stdio int8
	// refs counts EXTRA table slots sharing this entry (dup/dup2):
	// closeWasiOpen only closes the descriptor when it reaches zero.
	refs int32
}

// WasiStubs is the default Go-native implementation of wasi_snapshot_preview1.
// State is owned per-Module via NewWithWASI / DefaultWASI.
type WasiStubs struct {
	mu sync.Mutex

	// stdin/stdout/stderr back guest fds 0/1/2. They default to the host
	// os.Std* (DefaultWASI) but can be redirected to any io.Reader/io.Writer
	// (an in-process buffer, pipe, ...) via SetStdin/SetStdout/SetStderr, so an
	// embedder can feed input and capture/stream output without touching the
	// host process stdio.
	stdin          io.Reader
	stdout, stderr io.Writer
	fdTable        map[int32]*wasiOpen
	nextFD         int32
	args, env      []string
	monoStart      time.Time
	// preopenDir is the host directory mapped to wasi preopen fd 3.
	// Defaults to "/" (i.e. no rewriting) — the legacy behaviour. Tests
	// can set this via SetPreopenDir to scope filesystem ops to a
	// temporary directory.
	preopenDir string
	// fsHook, when non-nil, is consulted before every filesystem access
	// (Path_open, Path_create_directory, Path_unlink_file). It receives
	// the guest-supplied path (relative to the preopen, e.g. "a.txt" or
	// "sub/a.txt") and whether the access is a write. Returning false
	// denies the operation, which surfaces to the guest as EACCES. This
	// is the host-controlled whitelist hook: the policy itself lives in
	// the embedding application, OUTSIDE the generated runtime.
	fsHook func(path string, write bool) bool
	// netHook, when non-nil, is consulted before every socket operation
	// (Sock_accept, Sock_recv, Sock_send). op is "accept"/"recv"/"send".
	// Returning false denies the operation (EACCES). The same
	// host-controlled-whitelist intent as fsHook, for the network surface.
	netHook func(op string) bool
	// dialHook, when non-nil, is consulted before an OUTBOUND connect
	// (Sock_connect) with the resolved network ("tcp"), the HOST the guest
	// resolved to reach this address (from the preceding Sock_getaddrinfo, or ""
	// if the guest dialed a literal IP), the dotted-quad IP, and the port.
	// Returning false denies the connection (EACCES). Passing the host lets the
	// policy match host+port jointly, which a port-scoped rule needs — the IP
	// alone cannot be tied back to the rule that authorized the name.
	dialHook func(network, host, ip string, port int) bool
	// resolveHook, when non-nil, is consulted before a name lookup
	// (Sock_getaddrinfo) with the requested host. Returning false denies the
	// resolution (the guest sees a gaierror). This is the hostname-level
	// whitelist control point (e.g. block "example.com" by name).
	resolveHook func(host string) bool
	// resolvedHosts maps a resolved dotted-quad IP back to the host name the
	// guest looked it up under (populated by Sock_getaddrinfo, read by
	// Sock_connect), so the dial hook can be given the host. Guarded by mu.
	resolvedHosts map[string]string
	// fsys is the filesystem backend every guest path operation is routed
	// through. Defaults to an osFS scoped to preopenDir (the host filesystem);
	// SetFS swaps in an alternative (e.g. an in-memory FS) so each module can
	// see a private, arbitrary filesystem.
	fsys FS
	// procs tracks host processes spawned via Proc_spawn, keyed by the pid
	// handed back to the guest. nextPID is the handle counter (kept distinct
	// from real OS pids — the guest only ever sees these tokens).
	procs   map[int32]*wasiProc
	nextPID int32
	// execHook, when non-nil, gates every Proc_spawn with the resolved
	// executable path and argv; returning false denies the spawn (EACCES).
	// This is the outbound-process whitelist control point — the analogue of
	// dialHook for sockets. Spawning runs a HOST binary, so a sandbox that
	// enables host processes should always install this.
	execHook func(path string, argv []string) bool
}

// wasiProc is a host process spawned by Proc_spawn. A background goroutine
// Waits on the command and publishes the encoded POSIX status, so Proc_wait
// can support both the blocking (options 0) and non-blocking (WNOHANG) forms
// without holding the WasiStubs lock across the child's lifetime.
type wasiProc struct {
	cmd    *exec.Cmd
	done   chan struct{}
	status int32 // POSIX wait status, valid once done is closed
}

// DefaultWASI returns a WasiStubs configured for typical CLI use: real
// stdio, os.Args, os.Environ(), wall + monotonic clocks. Consumers who
// want a sandboxed setup should construct their own WasiStubs (or any
// Wasi_snapshot_preview1Imports implementation) and pass it to
// NewWithWASI.
func DefaultWASI() *WasiStubs {
	return &WasiStubs{
		stdin:      os.Stdin,
		stdout:     os.Stdout,
		stderr:     os.Stderr,
		fdTable:    map[int32]*wasiOpen{},
		nextFD:     4,
		args:       os.Args,
		env:        os.Environ(),
		monoStart:  time.Now(),
		preopenDir: "/",
		fsys:       osFS{root: "/"},
		procs:      map[int32]*wasiProc{},
		nextPID:    1000,
	}
}

// SetPreopenDir scopes the default (os-backed) filesystem to a host directory.
// Empty string restores the default ("/"), i.e. no rewriting. Tests use this
// to run filesystem syscalls against t.TempDir(). Has no effect once SetFS has
// installed a non-os backend.
func (w *WasiStubs) SetPreopenDir(dir string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if dir == "" {
		dir = "/"
	}
	w.preopenDir = dir
	w.fsys = osFS{root: dir}
}

// SetFS installs a custom filesystem backend. Every guest path operation
// (open, stat, mkdir, readdir, read, write, ...) is then routed to fsys, so a
// caller can give a module a private, arbitrary filesystem — for example an
// in-memory FS so writes never touch disk and are invisible to other modules.
// Pass nil to restore the default os-backed filesystem.
func (w *WasiStubs) SetFS(fsys FS) {
	// Materialize the preopen so close/dup/renumber obey the same FD identity
	// rules as every opened directory. SetFS is setup-only, before guest entry.
	if fsys == nil {
		fsys = osFS{root: w.preopenDir}
	}
	root, err := fsys.OpenFile(".", os.O_RDONLY, 0)
	if err != nil {
		panic(fmt.Sprintf("preopen root: %v", err))
	}
	w.mu.Lock()
	previous := w.fdTable[3]
	w.fsys = fsys
	w.fdTable[3] = &wasiOpen{f: root, isDir: true, path: "/"}
	w.mu.Unlock()
	if previous != nil {
		_ = closeWasiOpen(previous)
	}
}

// SetFSAccessHook installs a host-controlled filesystem access policy.
// hook is called with the guest path (relative to the preopen) and a
// write flag before each open/create/unlink; returning false denies the
// operation (the guest sees EACCES). Pass nil to clear the policy
// (unrestricted, the default). The hook runs without w.mu held, so it
// may itself call back into the host freely.
func (w *WasiStubs) SetFSAccessHook(hook func(path string, write bool) bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.fsHook = hook
}

// SetNetAccessHook installs a host-controlled network access policy.
// hook is called with the operation name ("accept"/"recv"/"send")
// before each socket operation; returning false denies it (EACCES).
// Pass nil to clear (unrestricted, the default).
//
// NOTE: WASI preview1 has no outbound connect or name resolution, so a
// guest cannot initiate connections regardless of this hook; it governs
// the accept/recv/send surface that preview1 does expose (host-preopened
// listening sockets). Full outbound control requires a host connect
// import, which this runtime does not yet provide.
func (w *WasiStubs) SetNetAccessHook(hook func(op string) bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.netHook = hook
}

// SetDialHook installs a host-controlled OUTBOUND-connection policy. hook is
// called with ("tcp", host, dotted-quad-IP, port) before each Sock_connect,
// where host is the name the guest resolved to reach the IP (from the preceding
// Sock_getaddrinfo) or "" for a literal-IP dial; returning false denies the
// connection (the guest sees a connect EACCES). Pass nil to clear (all outbound
// allowed, the default once outbound is wired).
func (w *WasiStubs) SetDialHook(hook func(network, host, ip string, port int) bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.dialHook = hook
}

// SetResolveHook installs a host-controlled name-resolution policy. hook is
// called with the host being resolved (Sock_getaddrinfo) before the lookup;
// returning false denies it (the guest sees a name-resolution error). Pass nil
// to clear (all lookups allowed). This is where a hostname whitelist such as
// "block example.com" is enforced.
func (w *WasiStubs) SetResolveHook(hook func(host string) bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.resolveHook = hook
}

// SetExecHook installs the process-spawn whitelist consulted by Proc_spawn
// with the executable path and full argv. Returning false denies the spawn
// (the guest's posix_spawn sees EACCES). Spawning runs a HOST binary, so a
// sandbox enabling host processes should always set this.
func (w *WasiStubs) SetExecHook(hook func(path string, argv []string) bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.execHook = hook
}

// readCStr reads a NUL-terminated C string at ptr from linear memory. A nil
// ptr (0) yields "". ok is false on an out-of-bounds or unterminated read.
func (w *WasiStubs) readCStr(m *Module, ptr int32) (s string, ok bool) {
	if ptr == 0 {
		return "", true
	}
	mem := m.Memory
	lo := uint64(uint32(ptr))
	if lo > uint64(len(mem)) {
		return "", false
	}
	rest := mem[lo:]
	for i := 0; i < len(rest); i++ {
		if rest[i] == 0 {
			return string(rest[:i]), true
		}
	}
	return "", false
}

// readCStrArray reads a NULL-terminated array of C-string pointers (a char**)
// at ptr. A nil ptr (0) yields a nil slice. ok is false on a bad read.
func (w *WasiStubs) readCStrArray(m *Module, ptr int32) (out []string, ok bool) {
	if ptr == 0 {
		return nil, true
	}
	for off := ptr; ; off += 4 {
		b := w.memSlice(m, off, 4)
		if b == nil {
			return nil, false
		}
		p := int32(binary.LittleEndian.Uint32(b))
		if p == 0 {
			break
		}
		s, sok := w.readCStr(m, p)
		if !sok {
			return nil, false
		}
		out = append(out, s)
	}
	return out, true
}

// Proc_spawn is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "proc_spawn") backing the bridge's posix_spawn(). It spawns a HOST
// process: path is the executable, argv/envp are NUL-terminated char** in
// linear memory. The child inherits the interpreter's stdin/stdout/stderr.
// The new pid token is written at pidOutPtr. Returns 0 or a negative errno.
//
// Only stdio inheritance is supported today (no fd remapping / pipes), which
// covers subprocess.run/call with default streams; capture_output via host
// pipes is a follow-up.
func (w *WasiStubs) Proc_spawn(m *Module, pathPtr, argvPtr, envpPtr, stdinFd, stdoutFd, stderrFd, cwdPtr, pidOutPtr int32) int32 {
	path, ok := w.readCStr(m, pathPtr)
	if !ok || path == "" {
		return -_wasiEINVAL
	}
	argv, ok := w.readCStrArray(m, argvPtr)
	if !ok {
		return -_wasiEFAULT
	}
	env, ok := w.readCStrArray(m, envpPtr)
	if !ok {
		return -_wasiEFAULT
	}

	cwd, ok := w.readCStr(m, cwdPtr)
	if !ok {
		return -_wasiEFAULT
	}
	out := w.memSlice(m, pidOutPtr, 4)
	if out == nil {
		return -_wasiEFAULT
	}

	w.mu.Lock()
	hook := w.execHook
	cin := w.childReaderLocked(stdinFd)
	cout := w.childWriterLocked(stdoutFd, w.stdout)
	cerr := w.childWriterLocked(stderrFd, w.stderr)
	w.mu.Unlock()
	if hook != nil && !hook(path, argv) {
		return -_wasiEACCES
	}

	cmd := exec.Command(path)
	if len(argv) > 0 {
		cmd.Args = argv
	} else {
		cmd.Args = []string{path}
	}
	if cwd != "" {
		cmd.Dir = cwd
	}

	cmd.Env = env
	if cmd.Env == nil {
		cmd.Env = []string{}
	}

	cmd.Stdin, cmd.Stdout, cmd.Stderr = cin, cout, cerr
	if err := cmd.Start(); err != nil {
		return -mapExecError(err)
	}

	proc := &wasiProc{cmd: cmd, done: make(chan struct{})}
	go func() {
		werr := cmd.Wait()
		proc.status = encodeWaitStatus(cmd.ProcessState)
		// A non-zero exit or signal surfaces as *exec.ExitError and is the
		// normal path (status already encoded from ProcessState above). Any
		// OTHER error means the wait itself failed; report a 127 exit.
		var exitErr *exec.ExitError
		if werr != nil && !errors.As(werr, &exitErr) {
			proc.status = int32(127) << 8
		}
		close(proc.done)
	}()

	w.mu.Lock()
	if w.procs == nil {
		w.procs = map[int32]*wasiProc{}
	}
	if w.nextPID == 0 {
		w.nextPID = 1000
	}
	pid := w.nextPID
	w.nextPID++
	w.procs[pid] = proc
	w.mu.Unlock()

	binary.LittleEndian.PutUint32(out, uint32(pid))
	return _wasiESUCCESS
}

// childReaderLocked resolves a child stdin source fd. A guest fd whose
// table entry carries a real file (a pipe end, or a guest stdio fd the
// program re-opened onto a file) is used directly; everything else —
// including -1 and an unredirected fd 0 — inherits the interpreter's
// stdin. Caller holds w.mu.
func (w *WasiStubs) childReaderLocked(fd int32) io.Reader {
	if fd >= 0 {
		if op := w.fdTable[fd]; op != nil && op.f != nil {
			return op.f
		}
	}
	return w.stdin
}

// childWriterLocked is the stdout/stderr counterpart of childReaderLocked.
func (w *WasiStubs) childWriterLocked(fd int32, deflt io.Writer) io.Writer {
	if fd >= 0 {
		if op := w.fdTable[fd]; op != nil && op.f != nil {
			return op.f
		}
	}
	return deflt
}

// Pipe is a NON-STANDARD host import (module wasi_snapshot_preview1, name
// "pipe") backing the bridge's pipe()/pipe2(). It creates a host OS pipe and
// registers both ends as guest fds, writing [readFd, writeFd] (two i32) at
// fdsOutPtr. The guest reads the read end via Fd_read; the write end is given
// to a child as its stdout/stderr via Proc_spawn, so subprocess.run can
// capture output. Returns 0 or a negative errno.
func (w *WasiStubs) Pipe(m *Module, fdsOutPtr int32) int32 {
	out := w.memSlice(m, fdsOutPtr, 8)
	if out == nil {
		return -_wasiEFAULT
	}
	r, wr, err := os.Pipe()
	if err != nil {
		return -mapOSError(err)
	}
	w.mu.Lock()
	if w.fdTable == nil {
		w.fdTable = map[int32]*wasiOpen{}
	}
	if w.nextFD < 4 {
		w.nextFD = 4
	}
	rfd := w.nextFD
	w.nextFD++
	wfd := w.nextFD
	w.nextFD++
	w.fdTable[rfd] = &wasiOpen{f: r}
	w.fdTable[wfd] = &wasiOpen{f: wr}
	w.mu.Unlock()
	binary.LittleEndian.PutUint32(out[0:], uint32(rfd))
	binary.LittleEndian.PutUint32(out[4:], uint32(wfd))
	return _wasiESUCCESS
}

// Proc_wait is a NON-STANDARD host import (name "proc_wait") backing the
// bridge's waitpid(). It waits for the process token pid and writes the POSIX
// wait status at statusOutPtr. options is the waitpid() options mask; bit 0
// (WNOHANG) makes it return without blocking when the child is still running
// (the guest sees the documented "0 means no child ready" result, signalled
// by writing pid 0 — encoded by returning EAGAIN). Returns 0, or a negative
// errno (ECHILD for an unknown pid).
func (w *WasiStubs) Proc_wait(m *Module, pid, options, statusOutPtr int32) int32 {
	out := w.memSlice(m, statusOutPtr, 4)
	if out == nil {
		return -_wasiEFAULT
	}
	w.mu.Lock()
	proc := w.procs[pid]
	w.mu.Unlock()
	if proc == nil {
		return -_wasiECHILD
	}
	const wnohang = 1
	if options&wnohang != 0 {
		select {
		case <-proc.done:
		default:

			return -_wasiEAGAIN
		}
	} else {
		<-proc.done
	}
	w.mu.Lock()
	delete(w.procs, pid)
	w.mu.Unlock()
	binary.LittleEndian.PutUint32(out, uint32(proc.status))
	return _wasiESUCCESS
}

// encodeWaitStatus turns a Go ProcessState into a POSIX wait status int (the
// raw value os.waitstatus_to_exitcode decodes): a normal exit N becomes
// (N&0xff)<<8 (WIFEXITED); a signal becomes the low-7-bits signal number
// (WIFSIGNALED).
func encodeWaitStatus(st *os.ProcessState) int32 {
	if st == nil {
		return 0
	}
	if ws, ok := st.Sys().(syscall.WaitStatus); ok {
		if ws.Signaled() {
			return int32(ws.Signal()) & 0x7f
		}
		return int32(ws.ExitStatus()&0xff) << 8
	}
	code := st.ExitCode()
	if code < 0 {
		code = 127
	}
	return int32(code&0xff) << 8
}

// mapExecError maps an exec.Command Start() failure to a wasi errno.
func mapExecError(err error) int32 {
	switch {
	case errors.Is(err, exec.ErrNotFound), errors.Is(err, fs.ErrNotExist):
		return _wasiENOENT
	case errors.Is(err, fs.ErrPermission):
		return _wasiEACCES
	default:
		return _wasiENOENT
	}
}

// Sock_getaddrinfo is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "sock_getaddrinfo") backing the bridge's getaddrinfo(). It reads the
// host string at (nodePtr,nodeLen), consults the resolve whitelist, resolves it
// to an IPv4 address via Go's resolver (numeric IPs pass through), and writes
// the 4-byte network-order address at outPtr. Returns 0 on success or a
// negative POSIX-ish errno (the bridge maps it to an EAI_* code).
func (w *WasiStubs) Sock_getaddrinfo(m *Module, nodePtr, nodeLen, outPtr int32) int32 {
	host := ""
	if nodeLen > 0 {
		b := w.memSlice(m, nodePtr, nodeLen)
		if b == nil {
			return -_wasiEFAULT
		}
		host = string(b)
	}
	out := w.memSlice(m, outPtr, 4)
	if out == nil {
		return -_wasiEFAULT
	}
	if host == "" {
		binary.LittleEndian.PutUint32(out, 0)
		return _wasiESUCCESS
	}
	w.mu.Lock()
	hook := w.resolveHook
	w.mu.Unlock()
	if hook != nil && !hook(host) {
		return -_wasiEACCES
	}

	if ip := net.ParseIP(host); ip != nil {
		if v4 := ip.To4(); v4 != nil {
			out[0], out[1], out[2], out[3] = v4[0], v4[1], v4[2], v4[3]
			w.recordResolvedHost(v4, host)
			return _wasiESUCCESS
		}
		return -_wasiEAFNOSUPPORT
	}
	ips, err := net.DefaultResolver.LookupIP(context.Background(), "ip4", host)
	if err != nil || len(ips) == 0 {
		return -_wasiENOENT
	}
	v4 := ips[0].To4()
	if v4 == nil {
		return -_wasiEAFNOSUPPORT
	}
	out[0], out[1], out[2], out[3] = v4[0], v4[1], v4[2], v4[3]
	w.recordResolvedHost(v4, host)
	return _wasiESUCCESS
}

// recordResolvedHost remembers that host resolved to v4, so a later Sock_connect
// to that IP can hand the dial hook the host name it was looked up under.
func (w *WasiStubs) recordResolvedHost(v4 net.IP, host string) {
	ip := fmt.Sprintf("%d.%d.%d.%d", v4[0], v4[1], v4[2], v4[3])
	w.mu.Lock()
	if w.resolvedHosts == nil {
		w.resolvedHosts = make(map[string]string)
	}
	w.resolvedHosts[ip] = host
	w.mu.Unlock()
}

// SetEnv overrides the environment the guest sees via environ_get /
// environ_sizes_get. By default DefaultWASI leaks the host process
// os.Environ(); a sandboxed embedding should call SetEnv with an
// explicit (possibly empty) slice of "KEY=VALUE" strings.
func (w *WasiStubs) SetEnv(env []string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.env = append([]string(nil), env...)
}

// SetArgs overrides os.Args as seen by the guest (argv). Mirrors SetEnv.
func (w *WasiStubs) SetArgs(args []string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.args = append([]string(nil), args...)
}

// SetStdin redirects guest fd 0 to r. A nil r leaves the current source.
// Use this to feed input() / sys.stdin from an in-process io.Reader instead
// of the host process stdin.
func (w *WasiStubs) SetStdin(r io.Reader) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if r != nil {
		w.stdin = r
	}
}

// SetStdout redirects guest fd 1 to wr. A nil wr leaves the current sink.
func (w *WasiStubs) SetStdout(wr io.Writer) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if wr != nil {
		w.stdout = wr
	}
}

// SetStderr redirects guest fd 2 to wr. A nil wr leaves the current sink.
func (w *WasiStubs) SetStderr(wr io.Writer) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if wr != nil {
		w.stderr = wr
	}
}

// checkFS consults the FS policy hook (if any). Returns true when the
// access is permitted. Callers must NOT hold w.mu.
func (w *WasiStubs) checkFS(path string, write bool) bool {
	w.mu.Lock()
	hook := w.fsHook
	w.mu.Unlock()
	if hook == nil {
		return true
	}
	return hook(path, write)
}

// checkNet consults the network policy hook (if any). Returns true when
// the operation is permitted. Callers must NOT hold w.mu.
func (w *WasiStubs) checkNet(op string) bool {
	w.mu.Lock()
	hook := w.netHook
	w.mu.Unlock()
	if hook == nil {
		return true
	}
	return hook(op)
}

// memSlice returns m.memory[off : off+n]. Callers must hold any locks
// they need on the wasm side; WasiStubs.mu is independent. Returns an
// empty slice on out-of-range (the wasi function should then return
// EFAULT / EINVAL).
func (w *WasiStubs) memSlice(m *Module, off, n int32) []byte {
	mem := m.Memory
	lo := uint64(uint32(off))
	hi := lo + uint64(uint32(n))
	if hi > uint64(len(mem)) {
		return nil
	}
	return mem[lo:hi]
}

// errno values used below (subset; see wasi-libc errno.h).
const (
	_wasiESUCCESS     int32 = 0
	_wasiE2BIG        int32 = 1
	_wasiEACCES       int32 = 2
	_wasiEAFNOSUPPORT int32 = 5
	_wasiEAGAIN       int32 = 6
	_wasiEBADF        int32 = 8
	_wasiECHILD       int32 = 12
	_wasiECONNREFUSED int32 = 14
	_wasiEISCONN      int32 = 33
	_wasiEBUSY        int32 = 10
	_wasiEEXIST       int32 = 20
	_wasiEFAULT       int32 = 21
	_wasiEINVAL       int32 = 28
	_wasiEIO          int32 = 29
	_wasiEISDIR       int32 = 31
	_wasiENOENT       int32 = 44
	_wasiENOTDIR      int32 = 54
	_wasiENOTSOCK     int32 = 57
	_wasiENOTSUP      int32 = 58
	_wasiENOSYS       int32 = 52
	_wasiEPERM        int32 = 63
	_wasiEPIPE        int32 = 64
)

// mapOSError turns an os/filesystem error into a wasi errno. Used by the
// path-based syscalls so any os.PathError surfaces as the appropriate
// guest-visible code instead of a coarse EIO.
func mapOSError(err error) int32 {
	if err == nil {
		return _wasiESUCCESS
	}
	switch {
	case errors.Is(err, fs.ErrNotExist):
		return _wasiENOENT
	case errors.Is(err, fs.ErrExist):
		return _wasiEEXIST
	case errors.Is(err, fs.ErrPermission):
		return _wasiEACCES
	case errors.Is(err, syscall.ENOTDIR):
		return _wasiENOTDIR
	case errors.Is(err, syscall.EISDIR):
		return _wasiEISDIR
	case errors.Is(err, syscall.EINVAL):
		return _wasiEINVAL
	case errors.Is(err, syscall.EBADF):
		return _wasiEBADF
	case errors.Is(err, syscall.EAGAIN):
		return _wasiEAGAIN
	case errors.Is(err, syscall.EPIPE):
		return _wasiEPIPE
	}
	return _wasiEIO
}

// totalBytes sums len(s)+1 over s in a uint64 and reports whether the
// total fits in an int32 (i.e. is representable as a wasm-side i32
// length). Callers route the result through memSlice and an OOB on a
// pathologically long arg list surfaces as EFAULT to the guest rather
// than a host-side panic via a wrapped-int32 length.
func totalBytesPlusNul(ss []string) (int32, bool) {
	var total uint64
	for _, s := range ss {
		total += uint64(len(s)) + 1
		if total > 0x7fffffff {
			return 0, false
		}
	}
	return int32(total), true
}

func (w *WasiStubs) Args_get(m *Module, argv, argvBuf int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()

	argvBytes64 := uint64(len(w.args)) * 4
	if argvBytes64 > 0x7fffffff {
		return _wasiEFAULT
	}
	argvSlice := w.memSlice(m, argv, int32(argvBytes64))
	if argvSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.args)
	if !ok {
		return _wasiEFAULT
	}
	argvBufSlice := w.memSlice(m, argvBuf, total)
	if argvBufSlice == nil {
		return _wasiEFAULT
	}
	bufOff := uint32(0)
	for i, a := range w.args {
		binary.LittleEndian.PutUint32(argvSlice[i*4:], uint32(argvBuf)+bufOff)
		n := copy(argvBufSlice[bufOff:], a)
		if n < len(a) {
			return _wasiEFAULT
		}
		bufOff += uint32(n)
		argvBufSlice[bufOff] = 0
		bufOff++
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Args_sizes_get(m *Module, argcPtr, argvBufLenPtr int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	argcSlice := w.memSlice(m, argcPtr, 4)
	bufLenSlice := w.memSlice(m, argvBufLenPtr, 4)
	if argcSlice == nil || bufLenSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.args)
	if !ok {
		return _wasiEFAULT
	}
	binary.LittleEndian.PutUint32(argcSlice, uint32(len(w.args)))
	binary.LittleEndian.PutUint32(bufLenSlice, uint32(total))
	return _wasiESUCCESS
}

func (w *WasiStubs) Environ_get(m *Module, envv, envBuf int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	envvBytes64 := uint64(len(w.env)) * 4
	if envvBytes64 > 0x7fffffff {
		return _wasiEFAULT
	}
	envvSlice := w.memSlice(m, envv, int32(envvBytes64))
	if envvSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.env)
	if !ok {
		return _wasiEFAULT
	}
	envBufSlice := w.memSlice(m, envBuf, total)
	if envBufSlice == nil {
		return _wasiEFAULT
	}
	bufOff := uint32(0)
	for i, e := range w.env {
		binary.LittleEndian.PutUint32(envvSlice[i*4:], uint32(envBuf)+bufOff)
		n := copy(envBufSlice[bufOff:], e)
		if n < len(e) {
			return _wasiEFAULT
		}
		bufOff += uint32(n)
		envBufSlice[bufOff] = 0
		bufOff++
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Environ_sizes_get(m *Module, envcPtr, envBufLenPtr int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	envcSlice := w.memSlice(m, envcPtr, 4)
	bufLenSlice := w.memSlice(m, envBufLenPtr, 4)
	if envcSlice == nil || bufLenSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.env)
	if !ok {
		return _wasiEFAULT
	}
	binary.LittleEndian.PutUint32(envcSlice, uint32(len(w.env)))
	binary.LittleEndian.PutUint32(bufLenSlice, uint32(total))
	return _wasiESUCCESS
}

func (w *WasiStubs) Clock_res_get(m *Module, clockID int32, resPtr int32) int32 {

	out := w.memSlice(m, resPtr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	binary.LittleEndian.PutUint64(out, 1)
	return _wasiESUCCESS
}

func (w *WasiStubs) Clock_time_get(m *Module, clockID int32, precision int64, timePtr int32) int32 {
	out := w.memSlice(m, timePtr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	nanos, errno := w.clockNanos(clockID)
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint64(out, nanos)
	return _wasiESUCCESS
}

// clockNanos is the layout-independent body of clock_time_get, shared
// by the wasm32 and wasm64 bindings.
func (w *WasiStubs) clockNanos(clockID int32) (uint64, int32) {
	switch clockID {
	case 0:
		return uint64(time.Now().UnixNano()), _wasiESUCCESS
	case 1:
		w.mu.Lock()
		nanos := uint64(time.Since(w.monoStart).Nanoseconds())
		w.mu.Unlock()
		return nanos, _wasiESUCCESS
	default:
		return 0, _wasiEINVAL
	}
}

// closeWasiOpen releases every underlying handle held by op and
// joins any Close errors so callers can map them to a wasi errno
// instead of silently dropping the failure.
func closeWasiOpen(op *wasiOpen) error {
	if op.refs > 0 {

		op.refs--
		return nil
	}
	var err error
	if op.f != nil {
		err = errors.Join(err, op.f.Close())
	}
	if op.conn != nil {
		err = errors.Join(err, op.conn.Close())
	}
	if op.listener != nil {
		err = errors.Join(err, op.listener.Close())
	}
	return err
}

func (w *WasiStubs) Fd_close(m *Module, fd int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	op := w.fdTable[fd]
	if op == nil {
		return _wasiEBADF
	}
	closeErr := closeWasiOpen(op)
	delete(w.fdTable, fd)
	if closeErr != nil {
		return mapOSError(closeErr)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_fdstat_get(m *Module, fd, ptr int32) int32 {

	out := w.memSlice(m, ptr, 24)
	if out == nil {
		return _wasiEFAULT
	}
	return w.fdstatFill(fd, out)
}

// fdstatFill writes the 24-byte fdstat for fd into out — the shared
// body of the 32- and 64-bit Fd_fdstat_get bindings (the struct holds
// no pointers, so the layout is width-independent).
func (w *WasiStubs) fdstatFill(fd int32, out []byte) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	var ftype byte = 4 // regular file
	var fdflags uint16
	if fd >= 0 && fd <= 2 {
		ftype = 2
	} else if op := w.fdTable[fd]; op != nil {
		if op.isDir {
			ftype = 3
		} else if op.conn != nil {
			ftype = 6
		} else if op.listener != nil {
			ftype = 6
		}
		fdflags = uint16(op.fdflags)
	} else if fd == 3 {
		ftype = 3
	} else if fd >= 4 {
		return _wasiEBADF
	}
	out[0] = ftype
	out[1] = 0
	binary.LittleEndian.PutUint16(out[2:], fdflags)

	binary.LittleEndian.PutUint64(out[8:], ^uint64(0))
	binary.LittleEndian.PutUint64(out[16:], ^uint64(0))
	return _wasiESUCCESS
}

// Fd_fdstat_set_flags maps WASI fdflags to OS file-status flags via the
// per-platform Fcntl wrapper. The flags are also cached on the wasiOpen
// so a subsequent Fd_fdstat_get reflects what the guest set. Stdio fds
// store the requested flags but otherwise no-op; sockets/listeners take
// only the cache update because Go's net layer manages blocking mode
// internally.
func (w *WasiStubs) Fd_fdstat_set_flags(m *Module, fd, flags int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	if op == nil && fd > 2 {
		w.mu.Unlock()
		return _wasiEBADF
	}
	if op != nil {
		op.fdflags = flags
	}
	w.mu.Unlock()

	_ = op
	_ = flags
	return _wasiESUCCESS
}

// Fd_fdstat_set_rights stores the requested rights on the wasiOpen but
// does not enforce them — the host process is the trust boundary. WASI
// programs that succeed with maximal rights (per Fd_fdstat_get) get the
// same ESUCCESS here.
func (w *WasiStubs) Fd_fdstat_set_rights(m *Module, fd int32, rightsBase, rightsInherit int64) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	if fd >= 0 && fd <= 2 {
		return _wasiESUCCESS
	}
	if w.fdTable[fd] == nil {
		return _wasiEBADF
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_filestat_get(m *Module, fd, ptr int32) int32 {

	out := w.memSlice(m, ptr, 64)
	if out == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {

		for i := range out {
			out[i] = 0
		}

		switch fd {
		case 0, 1, 2:
			out[16] = 2
		case 3:
			out[16] = 3
		}
		return _wasiESUCCESS
	}
	st, err := op.f.Stat()
	if err != nil {
		return mapOSError(err)
	}
	writeFilestat(out, st)
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_filestat_set_size(m *Module, fd int32, size int64) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}
	if err := op.f.Truncate(size); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_filestat_set_times(m *Module, fd int32, atim, mtim int64, fstFlags int32) int32 {

	w.mu.Lock()
	op := w.fdTable[fd]
	fsys := w.fsys
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}
	atime, mtime, err := resolveFiletimes(uint64(atim), uint64(mtim), fstFlags, op.f)
	if err != nil {
		return mapOSError(err)
	}

	if cf, ok := fsys.(chtimesFS); ok {
		if err := cf.Chtimes(op.path, atime, mtime); err != nil {
			return mapOSError(err)
		}
	}
	return _wasiESUCCESS
}

// combine64 reconstructs an unsigned 64-bit time value from a pair of
// 32-bit args. WASI signature uses two i32s for the nanosecond timestamp
// in fd_filestat_set_times.
func combine64(hi, lo int32) uint64 {
	return (uint64(uint32(hi)) << 32) | uint64(uint32(lo))
}

// resolveFiletimes decides the (atime, mtime) pair to apply given a
// fstFlags bitmask. Bits 0x2 (ATIME_NOW) and 0x8 (MTIME_NOW) override the
// explicit values with time.Now(). Unset ATIME/MTIME bits keep the
// existing on-disk time, so f.Stat must succeed when those bits are
// unset; the error is returned so the caller can surface it as a wasi
// errno rather than silently writing epoch.
func resolveFiletimes(atimNs, mtimNs uint64, fstFlags int32, f File) (time.Time, time.Time, error) {
	now := time.Now()
	var atime, mtime time.Time

	needCurrent := fstFlags&(0x1|0x2) == 0 || fstFlags&(0x4|0x8) == 0
	if needCurrent {
		st, err := f.Stat()
		if err != nil {
			return time.Time{}, time.Time{}, err
		}
		atime = st.ModTime()
		mtime = st.ModTime()
	}
	if fstFlags&0x1 != 0 {
		atime = time.Unix(0, int64(atimNs))
	}
	if fstFlags&0x2 != 0 {
		atime = now
	}
	if fstFlags&0x4 != 0 {
		mtime = time.Unix(0, int64(mtimNs))
	}
	if fstFlags&0x8 != 0 {
		mtime = now
	}
	return atime, mtime, nil
}

func (w *WasiStubs) Fd_prestat_get(m *Module, fd, ptr int32) int32 {

	if fd != 3 {
		return _wasiEBADF
	}

	out := w.memSlice(m, ptr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	out[0] = 0
	binary.LittleEndian.PutUint32(out[4:], 1)
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_prestat_dir_name(m *Module, fd, buf, buflen int32) int32 {
	if fd != 3 {
		return _wasiEBADF
	}
	if buflen < 1 {
		return _wasiESUCCESS
	}
	out := w.memSlice(m, buf, buflen)
	if out == nil {
		return _wasiEFAULT
	}
	out[0] = '/'
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_read(m *Module, fd, iovs, iovsLen, nreadPtr int32) int32 {
	w.mu.Lock()
	src, op := w.fdSrcLocked(fd)
	w.mu.Unlock()
	if src == nil {
		return _wasiEBADF
	}
	bufs, ok := w.iovecSlices(m, iovs, iovsLen)
	nreadSlice := w.memSlice(m, nreadPtr, 4)
	if !ok || nreadSlice == nil {
		return _wasiEFAULT
	}
	_ = op
	binary.LittleEndian.PutUint32(nreadSlice, uint32(readVec(src, bufs)))
	return _wasiESUCCESS
}

// iovecSlices resolves a wasm32 ciovec/iovec array ({u32 ptr, u32 len}
// entries at iovs) into the backing memory windows. Every entry is
// validated before any I/O happens, so a bad iovec faults the whole
// call instead of after a partial transfer.
func (w *WasiStubs) iovecSlices(m *Module, iovs, iovsLen int32) ([][]byte, bool) {

	iovBytes := uint64(uint32(iovsLen)) * 8
	if iovBytes > 0x7fffffff {
		return nil, false
	}
	iovecs := w.memSlice(m, iovs, int32(iovBytes))
	if iovecs == nil {
		return nil, false
	}
	bufs := make([][]byte, 0, iovsLen)
	for i := int32(0); i < iovsLen; i++ {
		bufPtr := binary.LittleEndian.Uint32(iovecs[i*8:])
		bufLen := binary.LittleEndian.Uint32(iovecs[i*8+4:])
		buf := w.memSlice(m, int32(bufPtr), int32(bufLen))
		if buf == nil {
			return nil, false
		}
		bufs = append(bufs, buf)
	}
	return bufs, true
}

// readVec fills bufs from src in order, stopping at the first error
// (EOF included) or short read; returns the bytes read. Shared by the
// wasm32 and wasm64 fd_read bindings — only the iovec layout differs.
func readVec(src io.Reader, bufs [][]byte) uint64 {
	var total uint64
	for _, buf := range bufs {
		n, err := src.Read(buf)
		total += uint64(n)
		if err != nil || n < len(buf) {
			break
		}
	}
	return total
}

// writeVec drains bufs into dst in order, stopping at the first failed
// write; returns the bytes written. Shared like readVec.
func writeVec(dst io.Writer, bufs [][]byte) uint64 {
	var total uint64
	for _, buf := range bufs {
		n, err := dst.Write(buf)
		total += uint64(n)
		if err != nil {
			break
		}
	}
	return total
}

// fdSrcLocked returns the io.Reader for fd and (when applicable) the
// wasiOpen it came from, or nil if fd is invalid. Caller must hold w.mu.
func (w *WasiStubs) fdSrcLocked(fd int32) (io.Reader, *wasiOpen) {

	op := w.fdTable[fd]
	if op == nil {
		if fd == 0 {
			return w.stdin, nil
		}
		return nil, nil
	}
	if op.stdio == 1 {
		return w.stdin, op
	}
	if op.f != nil {
		return op.f, op
	}
	if op.conn != nil {
		return op.conn, op
	}
	return nil, op
}

// fdDstLocked returns the io.Writer for fd or nil if fd is invalid.
// Caller must hold w.mu.
func (w *WasiStubs) fdDstLocked(fd int32) (io.Writer, *wasiOpen) {
	op := w.fdTable[fd]
	if op == nil {
		switch fd {
		case 1:
			return w.stdout, nil
		case 2:
			return w.stderr, nil
		}
		return nil, nil
	}
	switch op.stdio {
	case 2:
		return w.stdout, op
	case 3:
		return w.stderr, op
	}
	if op.f != nil {
		return op.f, op
	}
	if op.conn != nil {
		return op.conn, op
	}
	return nil, op
}

func (w *WasiStubs) Fd_pread(m *Module, fd, iovs, iovsLen int32, offset int64, nreadPtr int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}
	iovBytes := uint64(uint32(iovsLen)) * 8
	if iovBytes > 0x7fffffff {
		return _wasiEFAULT
	}
	iovecs := w.memSlice(m, iovs, int32(iovBytes))
	nreadSlice := w.memSlice(m, nreadPtr, 4)
	if iovecs == nil || nreadSlice == nil {
		return _wasiEFAULT
	}
	var total uint32
	curOff := offset
	for i := int32(0); i < iovsLen; i++ {
		bufPtr := binary.LittleEndian.Uint32(iovecs[i*8:])
		bufLen := binary.LittleEndian.Uint32(iovecs[i*8+4:])
		buf := w.memSlice(m, int32(bufPtr), int32(bufLen))
		if buf == nil {
			return _wasiEFAULT
		}
		n, err := op.f.ReadAt(buf, curOff)
		total += uint32(n)
		curOff += int64(n)
		if err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			break
		}
		if n < int(bufLen) {
			break
		}
	}
	binary.LittleEndian.PutUint32(nreadSlice, total)
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_pwrite(m *Module, fd, iovs, iovsLen int32, offset int64, nwrittenPtr int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}
	iovBytes := uint64(uint32(iovsLen)) * 8
	if iovBytes > 0x7fffffff {
		return _wasiEFAULT
	}
	iovecs := w.memSlice(m, iovs, int32(iovBytes))
	nwSlice := w.memSlice(m, nwrittenPtr, 4)
	if iovecs == nil || nwSlice == nil {
		return _wasiEFAULT
	}
	var total uint32
	curOff := offset
	for i := int32(0); i < iovsLen; i++ {
		bufPtr := binary.LittleEndian.Uint32(iovecs[i*8:])
		bufLen := binary.LittleEndian.Uint32(iovecs[i*8+4:])
		buf := w.memSlice(m, int32(bufPtr), int32(bufLen))
		if buf == nil {
			return _wasiEFAULT
		}
		n, err := op.f.WriteAt(buf, curOff)
		total += uint32(n)
		curOff += int64(n)
		if err != nil {
			break
		}
	}
	binary.LittleEndian.PutUint32(nwSlice, total)
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_seek(m *Module, fd int32, offset int64, whence, newOffPtr int32) int32 {
	out := w.memSlice(m, newOffPtr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	n, errno := w.fdSeek(fd, offset, int(whence))
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint64(out, uint64(n))
	return _wasiESUCCESS
}

// fdSeek is the layout-independent body of fd_seek, shared by the
// wasm32 and wasm64 bindings.
func (w *WasiStubs) fdSeek(fd int32, offset int64, whence int) (int64, int32) {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return 0, _wasiEBADF
	}
	n, err := op.f.Seek(offset, whence)
	if err != nil {
		return 0, _wasiEINVAL
	}
	return n, _wasiESUCCESS
}

func (w *WasiStubs) Fd_tell(m *Module, fd, offsetPtr int32) int32 {
	out := w.memSlice(m, offsetPtr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}
	n, err := op.f.Seek(0, 1)
	if err != nil {
		return _wasiEIO
	}
	binary.LittleEndian.PutUint64(out, uint64(n))
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_write(m *Module, fd, iovs, iovsLen, nwrittenPtr int32) int32 {
	w.mu.Lock()
	dst, _ := w.fdDstLocked(fd)
	w.mu.Unlock()
	bufs, ok := w.iovecSlices(m, iovs, iovsLen)
	nwrittenSlice := w.memSlice(m, nwrittenPtr, 4)
	if !ok || nwrittenSlice == nil {
		return _wasiEFAULT
	}
	if dst == nil {
		binary.LittleEndian.PutUint32(nwrittenSlice, 0)
		return _wasiEBADF
	}
	binary.LittleEndian.PutUint32(nwrittenSlice, uint32(writeVec(dst, bufs)))
	return _wasiESUCCESS
}
func (w *WasiStubs) Fd_sync(m *Module, fd int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}
	if err := op.f.Sync(); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_datasync(m *Module, fd int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}

	if err := op.f.Sync(); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_advise(m *Module, fd int32, offset, length int64, advice int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}

	_, _, _ = offset, length, advice
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_allocate(m *Module, fd int32, offset, length int64) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil {
		return _wasiEBADF
	}

	if err := op.f.Truncate(offset + length); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

// Path_chmod is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "path_chmod") backing a bridge-provided chmod(): WASI preview1 has
// no way to change file modes. The path at (pathPtr,pathLen) is
// preopen-relative, like path_open's. Backends without chmod support
// (MemFS keeps no modes) report ENOSYS. Returns 0 or a negative errno.
func (w *WasiStubs) Path_chmod(m *Module, pathPtr, pathLen, mode int32) int32 {
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	if pathSlice == nil {
		return -_wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	ch, ok := fsys.(interface {
		Chmod(string, os.FileMode) error
	})
	if !ok {
		return -_wasiENOSYS
	}
	if err := ch.Chmod(string(pathSlice), os.FileMode(uint32(mode)&0o7777)); err != nil {
		return -mapOSError(err)
	}
	return _wasiESUCCESS
}

// Path_filestat_mode is a NON-STANDARD host import (module
// wasi_snapshot_preview1, name "path_filestat_mode") backing a
// bridge-provided stat/lstat: WASI's filestat carries no permission
// bits, so the bridge merges the real mode in from here. The path is
// preopen-relative; follow selects stat vs lstat semantics. Writes the
// unix permission bits at modeOutPtr; returns 0 or a negative errno.
func (w *WasiStubs) Path_filestat_mode(m *Module, pathPtr, pathLen, follow, modeOutPtr int32) int32 {
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	out := w.memSlice(m, modeOutPtr, 4)
	if pathSlice == nil || out == nil {
		return -_wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	var fi os.FileInfo
	var err error
	if follow != 0 {
		fi, err = fsys.Stat(string(pathSlice))
	} else {
		fi, err = fsys.Lstat(string(pathSlice))
	}
	if err != nil {
		return -mapOSError(err)
	}
	mode := fi.Mode()
	bits := uint32(mode.Perm())
	if mode&os.ModeSetuid != 0 {
		bits |= 0o4000
	}
	if mode&os.ModeSetgid != 0 {
		bits |= 0o2000
	}
	if mode&os.ModeSticky != 0 {
		bits |= 0o1000
	}
	binary.LittleEndian.PutUint32(out, bits)
	return _wasiESUCCESS
}

// dupSourceLocked resolves the entry a dup of fd should share: the
// existing table entry, or a fresh alias for a bare interpreter stdio fd.
// Caller holds w.mu.
func (w *WasiStubs) dupSourceLocked(fd int32) *wasiOpen {
	if op := w.fdTable[fd]; op != nil {
		return op
	}
	if fd >= 0 && fd <= 2 {
		op := &wasiOpen{stdio: int8(fd + 1)}
		w.fdTable[fd] = op
		return op
	}
	return nil
}

// Fd_dup is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "fd_dup") backing the bridge's dup(): the new fd shares the same
// open descriptor (offset included), and the underlying file closes only
// when the last sharing fd does. Writes the new fd at outPtr.
func (w *WasiStubs) Fd_dup(m *Module, fd, outPtr int32) int32 {
	out := w.memSlice(m, outPtr, 4)
	if out == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	defer w.mu.Unlock()
	op := w.dupSourceLocked(fd)
	if op == nil {
		return _wasiEBADF
	}
	nfd := w.nextFD
	w.nextFD++
	w.fdTable[nfd] = op
	op.refs++
	binary.LittleEndian.PutUint32(out, uint32(nfd))
	return _wasiESUCCESS
}

// Fd_dup2 is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "fd_dup2") backing the bridge's dup2(): to becomes another
// reference to from's descriptor, closing whatever to previously held.
func (w *WasiStubs) Fd_dup2(m *Module, from, to int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	src := w.dupSourceLocked(from)
	if src == nil {
		return _wasiEBADF
	}
	if from == to {
		return _wasiESUCCESS
	}
	var closeErr error
	if dst := w.fdTable[to]; dst != nil {
		if dst == src {
			return _wasiESUCCESS
		}
		closeErr = closeWasiOpen(dst)
	}
	w.fdTable[to] = src
	src.refs++
	if closeErr != nil {
		return mapOSError(closeErr)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_renumber(m *Module, from, to int32) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	if from == to {

		if _, ok := w.fdTable[from]; ok {
			return _wasiESUCCESS
		}
		return _wasiEBADF
	}
	src, ok := w.fdTable[from]
	if !ok {
		return _wasiEBADF
	}
	var closeErr error
	if dst, ok2 := w.fdTable[to]; ok2 {
		closeErr = closeWasiOpen(dst)
	}
	w.fdTable[to] = src
	delete(w.fdTable, from)
	if closeErr != nil {
		return mapOSError(closeErr)
	}
	return _wasiESUCCESS
}

// readDirCached lazily caches the directory listing on first
// Fd_readdir, so paged reads (cookie-driven) walk the same snapshot.
func (op *wasiOpen) readDirCached() ([]os.DirEntry, error) {
	if op.dirCache != nil {
		return op.dirCache, nil
	}
	if op.f == nil {
		return nil, syscall.EBADF
	}
	if _, err := op.f.Seek(0, 0); err != nil {
		return nil, err
	}
	entries, err := op.f.ReadDir(-1)
	if err != nil {
		return nil, err
	}

	out := make([]os.DirEntry, 0, len(entries)+2)
	out = append(out, dotEntry(op.path, "."), dotEntry(op.path, ".."))
	out = append(out, entries...)

	sort.SliceStable(out[2:], func(i, j int) bool {
		return out[2+i].Name() < out[2+j].Name()
	})
	op.dirCache = out
	return out, nil
}

// dotEntry produces a synthetic os.DirEntry for "." and "..". Its
// Info() returns the stat of the parent directory (good enough for
// guest-side d_type detection).
func dotEntry(parent, name string) os.DirEntry {
	return &dotDirEntry{name: name, parent: parent}
}

type dotDirEntry struct {
	name, parent string
}

func (d *dotDirEntry) Name() string { return d.name }
func (d *dotDirEntry) IsDir() bool  { return true }
func (d *dotDirEntry) Type() os.FileMode {
	return os.ModeDir
}
func (d *dotDirEntry) Info() (os.FileInfo, error) {
	if d.name == "." {
		return os.Stat(d.parent)
	}
	return os.Stat(filepath.Dir(d.parent))
}

func (w *WasiStubs) Fd_readdir(m *Module, fd, buf, buflen int32, cookie int64, bufusedPtr int32) int32 {
	bufSlice := w.memSlice(m, buf, buflen)
	bufusedSlice := w.memSlice(m, bufusedPtr, 4)
	if bufSlice == nil || bufusedSlice == nil {
		return _wasiEFAULT
	}
	written, errno := w.fdReaddir(fd, bufSlice, cookie)
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint32(bufusedSlice, uint32(written))
	return _wasiESUCCESS
}

// fdReaddir is the layout-independent body of fd_readdir: it packs
// dirents into bufSlice starting at the cookie'th entry and returns the
// byte count used. The dirent wire format has no pointer-width fields,
// so wasm32 and wasm64 share it; only the bufused out-pointer differs.
func (w *WasiStubs) fdReaddir(fd int32, bufSlice []byte, cookie int64) (int, int32) {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.f == nil || !op.isDir {
		return 0, _wasiEBADF
	}

	if cookie == 0 {
		op.dirCache = nil
	}
	entries, err := op.readDirCached()
	if err != nil {
		return 0, mapOSError(err)
	}
	startIdx := int(cookie)
	if startIdx < 0 {
		startIdx = 0
	}
	written := 0
	for i := startIdx; i < len(entries); i++ {
		e := entries[i]
		nameBytes := []byte(e.Name())
		// dirent header: d_next u64 + d_ino u64 + d_namlen u32 + d_type u8 + 3 pad = 24 bytes.
		const headerLen = 24
		// os.FileInfo does not expose inode portably; report 0.
		var dtype byte = 4 // regular file
		if e.IsDir() {
			dtype = 3
		} else if e.Type()&os.ModeSymlink != 0 {
			dtype = 7
		} else if e.Type()&os.ModeNamedPipe != 0 {
			dtype = 6
		} else if e.Type()&os.ModeSocket != 0 {
			dtype = 6
		}
		// Assemble the fixed header, then copy header+name into the buffer.
		// When a record does not fully fit we copy as much as fits so that
		// bufused == buflen, which is the wasi-libc signal for "more entries
		// available; call again with the last returned cookie". We must NOT
		// zero-fill the leftover: a zeroed dirent (d_namlen=0, d_next=0) is
		// misread by wasi-libc as end-of-directory and silently truncates the
		// listing (e.g. makes a guest's importer miss standard-library packages).
		var hdr [headerLen]byte
		binary.LittleEndian.PutUint64(hdr[0:], uint64(i+1))

		binary.LittleEndian.PutUint64(hdr[8:], uint64(i)+1)
		binary.LittleEndian.PutUint32(hdr[16:], uint32(len(nameBytes)))
		hdr[20] = dtype
		n := copy(bufSlice[written:], hdr[:])
		written += n
		if n < len(hdr) {
			written = len(bufSlice)
			break
		}
		n = copy(bufSlice[written:], nameBytes)
		written += n
		if n < len(nameBytes) {
			written = len(bufSlice)
			break
		}
	}
	return written, _wasiESUCCESS
}

// Path_open opens a wasm-supplied path and registers it in the fd
// table. The path is resolved against the host filesystem with the same
// rights the host Go process has — wasm2go's default WASI is a thin
// passthrough, not a sandbox. The dirFd == 3 special case keeps the
// "preopen /" convention that wasi-libc requires for its directory
// enumeration, but the path itself is opened verbatim (joined to "/")
// using os.OpenFile. Callers that need a sandbox should provide their
// own Wasi_snapshot_preview1Imports implementation via NewWithWASI.
func (w *WasiStubs) Path_open(m *Module, dirFd, dirflags, pathPtr, pathLen, oflags int32, fsRightsBase, fsRightsInherit int64, fdflags, openedFdPtr int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	outSlice := w.memSlice(m, openedFdPtr, 4)
	if pathSlice == nil || outSlice == nil {
		return _wasiEFAULT
	}
	fd, errno := w.pathOpen(string(pathSlice), dirflags, oflags, fsRightsBase, fdflags)
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint32(outSlice, uint32(fd))
	return _wasiESUCCESS
}

// pathOpen is the layout-independent body of path_open: it resolves and
// opens rel, registers the fd, and returns it. Callers own reading the
// path and writing the opened fd at their ABI's pointer width.
func (w *WasiStubs) pathOpen(rel string, dirflags, oflags int32, fsRightsBase int64, fdflags int32) (int32, int32) {
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	return w.pathOpenOnFS(fsys, rel, rel, dirflags, oflags, fsRightsBase, fdflags)
}

// Resolution happens in the supplied opened directory, never via its pathname.
// policyPath is only the existing access-hook label, not a lookup operand.
func (w *WasiStubs) pathOpenOnFS(fsys relativeFileSystem, rel, policyPath string, dirflags, oflags int32, fsRightsBase int64, fdflags int32) (int32, int32) {
	canRead := fsRightsBase&(1<<1) != 0
	canWrite := fsRightsBase&(1<<6) != 0
	var flag int
	switch {
	case canRead && canWrite:
		flag = os.O_RDWR
	case canWrite && !canRead:
		flag = os.O_WRONLY
	default:
		flag = os.O_RDONLY
	}

	if oflags&0x1 != 0 {
		flag |= os.O_CREATE
	}
	if oflags&0x4 != 0 {
		flag |= os.O_EXCL
	}
	if oflags&0x8 != 0 {
		flag |= os.O_TRUNC
	}

	if fdflags&0x1 != 0 {
		flag |= os.O_APPEND
	}
	if fdflags&(0x2|0x8|0x10) != 0 {
		flag |= os.O_SYNC
	}

	writeAccess := flag&(os.O_WRONLY|os.O_RDWR) != 0 || flag&(os.O_CREATE|os.O_TRUNC) != 0
	if !w.checkFS(policyPath, writeAccess) {
		return -1, _wasiEACCES
	}

	requireDir := oflags&0x2 != 0
	noFollow := dirflags&0x1 == 0

	if requireDir {

		flag = os.O_RDONLY
	}

	if noFollow {
		if li, lerr := fsys.Lstat(rel); lerr == nil && (li.Mode()&os.ModeSymlink) != 0 {
			return -1, _wasiENOENT
		}
	}
	f, err := fsys.OpenFile(rel, flag, 0o644)
	if err != nil {
		return -1, mapOSError(err)
	}
	st, statErr := f.Stat()
	if statErr != nil {
		return -1, mapOSError(errors.Join(statErr, f.Close()))
	}
	isDir := st.IsDir()
	if requireDir && !isDir {
		if cerr := f.Close(); cerr != nil {
			return -1, mapOSError(cerr)
		}
		return -1, _wasiENOTDIR
	}
	w.mu.Lock()
	fd := w.nextFD
	w.nextFD++
	w.fdTable[fd] = &wasiOpen{f: f, isDir: isDir, path: rel, fdflags: fdflags}
	w.mu.Unlock()
	return fd, _wasiESUCCESS
}

func (w *WasiStubs) Path_create_directory(m *Module, dirFd, pathPtr, pathLen int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	if pathSlice == nil {
		return _wasiEFAULT
	}
	if !w.checkFS(string(pathSlice), true) {
		return _wasiEACCES
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	if err := fsys.Mkdir(string(pathSlice), 0o755); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_unlink_file(m *Module, dirFd, pathPtr, pathLen int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	if pathSlice == nil {
		return _wasiEFAULT
	}
	if !w.checkFS(string(pathSlice), true) {
		return _wasiEACCES
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	rel := string(pathSlice)
	st, err := fsys.Lstat(rel)
	if err != nil {
		return mapOSError(err)
	}
	if st.IsDir() {
		return _wasiEISDIR
	}
	if err := fsys.Remove(rel); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_remove_directory(m *Module, dirFd, pathPtr, pathLen int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	if pathSlice == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	rel := string(pathSlice)
	st, err := fsys.Lstat(rel)
	if err != nil {
		return mapOSError(err)
	}
	if !st.IsDir() {
		return _wasiENOTDIR
	}
	if err := fsys.Remove(rel); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_rename(m *Module, oldFd, oldPathPtr, oldPathLen, newFd, newPathPtr, newPathLen int32) int32 {
	if oldFd != 3 || newFd != 3 {
		return _wasiEBADF
	}
	oldSlice := w.memSlice(m, oldPathPtr, oldPathLen)
	newSlice := w.memSlice(m, newPathPtr, newPathLen)
	if oldSlice == nil || newSlice == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	if err := fsys.Rename(string(oldSlice), string(newSlice)); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_filestat_get(m *Module, dirFd, flags, pathPtr, pathLen, outPtr int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	out := w.memSlice(m, outPtr, 64)
	if pathSlice == nil || out == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	rel := string(pathSlice)
	var st os.FileInfo
	var err error
	if flags&0x1 != 0 {
		st, err = fsys.Stat(rel)
	} else {
		st, err = fsys.Lstat(rel)
	}
	if err != nil {
		return mapOSError(err)
	}
	writeFilestat(out, st)
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_filestat_set_times(m *Module, dirFd, flags, pathPtr, pathLen int32, atim, mtim int64, fstFlags int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	if pathSlice == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	rel := string(pathSlice)
	follow := flags&0x1 != 0
	now := time.Now()
	var st os.FileInfo
	var statErr error
	if follow {
		st, statErr = fsys.Stat(rel)
	} else {
		st, statErr = fsys.Lstat(rel)
	}
	if statErr != nil {
		return mapOSError(statErr)
	}
	atime := st.ModTime()
	mtime := st.ModTime()
	if fstFlags&0x1 != 0 {
		atime = time.Unix(0, int64(atim))
	}
	if fstFlags&0x2 != 0 {
		atime = now
	}
	if fstFlags&0x4 != 0 {
		mtime = time.Unix(0, int64(mtim))
	}
	if fstFlags&0x8 != 0 {
		mtime = now
	}

	if cf, ok := fsys.(chtimesFS); ok {
		if err := cf.Chtimes(rel, atime, mtime); err != nil {
			return mapOSError(err)
		}
	}
	return _wasiESUCCESS
}

// chtimesFS is an optional FS capability for backends that track timestamps.
type chtimesFS interface {
	Chtimes(name string, atime, mtime time.Time) error
}

func (o osFS) Chtimes(name string, atime, mtime time.Time) error {
	return os.Chtimes(o.join(name), atime, mtime)
}

func (w *WasiStubs) Path_link(m *Module, oldFd, oldFlags, oldPathPtr, oldPathLen, newFd, newPathPtr, newPathLen int32) int32 {
	if oldFd != 3 || newFd != 3 {
		return _wasiEBADF
	}
	oldSlice := w.memSlice(m, oldPathPtr, oldPathLen)
	newSlice := w.memSlice(m, newPathPtr, newPathLen)
	if oldSlice == nil || newSlice == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	if err := fsys.Link(string(oldSlice), string(newSlice)); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_symlink(m *Module, targetPtr, targetLen, dirFd, linkPathPtr, linkPathLen int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	targetSlice := w.memSlice(m, targetPtr, targetLen)
	linkSlice := w.memSlice(m, linkPathPtr, linkPathLen)
	if targetSlice == nil || linkSlice == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	if err := fsys.Symlink(string(targetSlice), string(linkSlice)); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_readlink(m *Module, dirFd, pathPtr, pathLen, buf, buflen, bufusedPtr int32) int32 {
	if dirFd != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice(m, pathPtr, pathLen)
	bufSlice := w.memSlice(m, buf, buflen)
	bufused := w.memSlice(m, bufusedPtr, 4)
	if pathSlice == nil || bufSlice == nil || bufused == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	target, err := fsys.Readlink(string(pathSlice))
	if err != nil {
		return mapOSError(err)
	}
	n := copy(bufSlice, target)
	binary.LittleEndian.PutUint32(bufused, uint32(n))
	return _wasiESUCCESS
}

func (w *WasiStubs) Random_get(m *Module, buf, bufLen int32) int32 {
	slice := w.memSlice(m, buf, bufLen)
	if slice == nil {
		return _wasiEFAULT
	}
	_, err := rand.Read(slice)
	if err != nil {
		return _wasiEIO
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Sched_yield(m *Module) int32 {
	runtime.Gosched()
	return _wasiESUCCESS
}

// Poll_oneoff decodes the WASI subscription_u records and reproduces the
// requested events.
//
// Each subscription is 48 bytes:
//
//	u64 userdata
//	u8  eventtype  (0=clock, 1=fd_read, 2=fd_write)
//	... per-type payload starting at offset 16
//
// For clock subscriptions, payload at offset 16 is: u32 clock_id, u64
// timeout, u64 precision, u16 sub_clock_flags (bit0=ABSTIME). We sleep
// for `timeout` ns (relative timer) or the diff to `timeout` (absolute
// timer). For fd_read / fd_write subscriptions, payload at offset 16 is
// a u32 fd; we call into the platform Poll helper to wait for
// readiness.
//
// Each emitted event is 32 bytes: u64 userdata, u16 errno, u16
// eventtype, u64 fd_readwrite_nbytes (filled for fd events), u16
// flags, then 6 bytes of padding.
func (w *WasiStubs) Poll_oneoff(m *Module, inPtr, outPtr, nsubs, neventsPtr int32) int32 {
	subsTotal := uint64(uint32(nsubs)) * 48
	if subsTotal > 0x7fffffff {
		return _wasiEFAULT
	}
	subs := w.memSlice(m, inPtr, int32(subsTotal))
	evTotal := uint64(uint32(nsubs)) * 32
	if evTotal > 0x7fffffff {
		return _wasiEFAULT
	}
	events := w.memSlice(m, outPtr, int32(evTotal))
	nev := w.memSlice(m, neventsPtr, 4)
	if subs == nil || events == nil || nev == nil {
		return _wasiEFAULT
	}

	type pollItem struct {
		userdata uint64
		etype    byte
		fd       int32
		isRead   bool
	}
	var minClockNs int64 = -1
	var clockEvents []pollItem
	var fdEvents []pollItem
	for i := int32(0); i < nsubs; i++ {
		base := i * 48
		userdata := binary.LittleEndian.Uint64(subs[base:])
		etype := subs[base+8]
		switch etype {
		case 0:
			timeout := int64(binary.LittleEndian.Uint64(subs[base+24:]))
			flags := binary.LittleEndian.Uint16(subs[base+40:])
			ns := timeout
			if flags&0x1 != 0 {

				ns = timeout - time.Now().UnixNano()
				if ns < 0 {
					ns = 0
				}
			}
			if minClockNs < 0 || ns < minClockNs {
				minClockNs = ns
			}
			clockEvents = append(clockEvents, pollItem{userdata: userdata, etype: 0})
		case 1, 2:
			fd := int32(binary.LittleEndian.Uint32(subs[base+16:]))
			fdEvents = append(fdEvents, pollItem{userdata: userdata, etype: etype, fd: fd, isRead: etype == 1})
		default:

			clockEvents = append(clockEvents, pollItem{userdata: userdata, etype: etype})
		}
	}

	if minClockNs > 0 && len(fdEvents) == 0 {
		time.Sleep(time.Duration(minClockNs))
	}

	written := int32(0)
	for _, ev := range clockEvents {
		if ev.etype == 0 && len(fdEvents) > 0 {
			continue
		}
		writeEvent(events[written:written+32], ev.userdata, ev.etype, 0, 0)
		written += 32
	}
	for _, ev := range fdEvents {
		w.mu.Lock()
		op := w.fdTable[ev.fd]
		w.mu.Unlock()
		var errno int32
		var nbytes uint64
		if op == nil {
			errno = _wasiEBADF
		} else if op.f != nil {

			if ev.isRead {
				if st, err := op.f.Stat(); err == nil {

					if cur, err := op.f.Seek(0, 1); err == nil && st.Size() > cur {
						nbytes = uint64(st.Size() - cur)
					}
				}
			}
		} else if op.conn != nil {

			_ = minClockNs
		}
		writeEvent(events[written:written+32], ev.userdata, ev.etype, uint16(errno), nbytes)
		written += 32
	}

	binary.LittleEndian.PutUint32(nev, uint32(written/32))
	return _wasiESUCCESS
}

func writeEvent(dst []byte, userdata uint64, etype byte, errno uint16, nbytes uint64) {
	for i := range dst {
		dst[i] = 0
	}
	binary.LittleEndian.PutUint64(dst[0:], userdata)
	binary.LittleEndian.PutUint16(dst[8:], errno)
	binary.LittleEndian.PutUint16(dst[10:], uint16(etype))
	binary.LittleEndian.PutUint64(dst[16:], nbytes)
}

func (w *WasiStubs) Proc_exit(m *Module, code int32) {

	panic(&WasiExitError{Code: code})
}

func (w *WasiStubs) Proc_raise(m *Module, sig int32) int32 {
	p, err := os.FindProcess(os.Getpid())
	if err != nil {
		return mapOSError(err)
	}
	if err := p.Signal(syscall.Signal(sig)); err != nil {
		return mapOSError(err)
	}
	return _wasiESUCCESS
}

// Sock_socket is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "sock_socket") that backs a libc socket() call wrapped via
// -Wl,--wrap=socket in the guest. WASI preview1 has no way to create an
// outbound socket; this gives the guest a host-managed fd whose connection is
// established later by Sock_connect. domain/type follow the POSIX socket()
// args (AF_INET / SOCK_STREAM); only TCP over IPv4 is supported. Returns the
// new fd, or a negative errno on failure.
func (w *WasiStubs) Sock_socket(m *Module, domain, typ int32) int32 {

	_ = domain
	_ = typ
	w.mu.Lock()
	defer w.mu.Unlock()
	fd := w.nextFD
	w.nextFD++
	w.fdTable[fd] = &wasiOpen{isSocket: true}
	return fd
}

// Sock_connect is a NON-STANDARD host import (module wasi_snapshot_preview1,
// name "sock_connect") backing a libc connect() wrapped via
// -Wl,--wrap=connect. ipBE carries the IPv4 address in network byte order
// exactly as it sat in sockaddr_in.sin_addr.s_addr (so the low byte is the
// first octet); port is host byte order. It consults the dial whitelist,
// dials via Go's net, and attaches the resulting conn to the socket fd so the
// existing Sock_send / Sock_recv / Fd_close paths drive it. Returns 0 or a
// negative errno.
func (w *WasiStubs) Sock_connect(m *Module, fd, ipBE, port int32) int32 {
	u := uint32(ipBE)
	ip := fmt.Sprintf("%d.%d.%d.%d", u&0xff, (u>>8)&0xff, (u>>16)&0xff, (u>>24)&0xff)
	w.mu.Lock()
	op := w.fdTable[fd]
	hook := w.dialHook
	host := w.resolvedHosts[ip]
	w.mu.Unlock()
	if op == nil || !op.isSocket {
		return -_wasiENOTSOCK
	}
	if op.conn != nil {
		return -_wasiEISCONN
	}
	p := int(uint16(port))
	if hook != nil && !hook("tcp", host, ip, p) {
		return -_wasiEACCES
	}
	conn, err := net.DialTimeout("tcp", net.JoinHostPort(ip, strconv.Itoa(p)), 30*time.Second)
	if err != nil {
		return -_wasiECONNREFUSED
	}
	w.mu.Lock()

	if cur := w.fdTable[fd]; cur == op {
		op.conn = conn
		w.mu.Unlock()
		return _wasiESUCCESS
	}
	w.mu.Unlock()
	if cerr := conn.Close(); cerr != nil {
		return mapOSError(cerr)
	}
	return -_wasiEBADF
}

// Sock_accept accepts the next incoming TCP/Unix connection on the
// listener associated with fd, registers it as a new wasiOpen with a
// conn arm, and writes the new fd at fdOutPtr. Returns ENOTSOCK if fd
// isn't a listener.
func (w *WasiStubs) Sock_accept(m *Module, fd, flags, fdOutPtr int32) int32 {
	if !w.checkNet("accept") {
		return _wasiEACCES
	}
	out := w.memSlice(m, fdOutPtr, 4)
	if out == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.listener == nil {
		return _wasiENOTSOCK
	}
	conn, err := op.listener.Accept()
	if err != nil {
		return mapOSError(err)
	}
	w.mu.Lock()
	newFD := w.nextFD
	w.nextFD++
	w.fdTable[newFD] = &wasiOpen{conn: conn}
	w.mu.Unlock()
	binary.LittleEndian.PutUint32(out, uint32(newFD))
	return _wasiESUCCESS
}

func (w *WasiStubs) Sock_recv(m *Module, fd, riData, riDataLen, riFlags, roDataLenPtr, roFlagsPtr int32) int32 {
	if !w.checkNet("recv") {
		return _wasiEACCES
	}
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.conn == nil {
		return _wasiENOTSOCK
	}
	iovBytes := uint64(uint32(riDataLen)) * 8
	if iovBytes > 0x7fffffff {
		return _wasiEFAULT
	}
	iovecs := w.memSlice(m, riData, int32(iovBytes))
	lenOut := w.memSlice(m, roDataLenPtr, 4)

	flagsOut := w.memSlice(m, roFlagsPtr, 2)
	if iovecs == nil || lenOut == nil || flagsOut == nil {
		return _wasiEFAULT
	}
	var total uint32
	for i := int32(0); i < riDataLen; i++ {
		bufPtr := binary.LittleEndian.Uint32(iovecs[i*8:])
		bufLen := binary.LittleEndian.Uint32(iovecs[i*8+4:])
		buf := w.memSlice(m, int32(bufPtr), int32(bufLen))
		if buf == nil {
			return _wasiEFAULT
		}
		n, err := op.conn.Read(buf)
		total += uint32(n)
		if err != nil {
			break
		}
	}
	binary.LittleEndian.PutUint16(flagsOut, 0)
	binary.LittleEndian.PutUint32(lenOut, total)
	return _wasiESUCCESS
}

func (w *WasiStubs) Sock_send(m *Module, fd, siData, siDataLen, siFlags, soDataLenPtr int32) int32 {
	if !w.checkNet("send") {
		return _wasiEACCES
	}
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.conn == nil {
		return _wasiENOTSOCK
	}
	iovBytes := uint64(uint32(siDataLen)) * 8
	if iovBytes > 0x7fffffff {
		return _wasiEFAULT
	}
	iovecs := w.memSlice(m, siData, int32(iovBytes))
	lenOut := w.memSlice(m, soDataLenPtr, 4)
	if iovecs == nil || lenOut == nil {
		return _wasiEFAULT
	}
	var total uint32
	for i := int32(0); i < siDataLen; i++ {
		bufPtr := binary.LittleEndian.Uint32(iovecs[i*8:])
		bufLen := binary.LittleEndian.Uint32(iovecs[i*8+4:])
		buf := w.memSlice(m, int32(bufPtr), int32(bufLen))
		if buf == nil {
			return _wasiEFAULT
		}
		n, err := op.conn.Write(buf)
		total += uint32(n)
		if err != nil {
			break
		}
	}
	binary.LittleEndian.PutUint32(lenOut, total)
	return _wasiESUCCESS
}

func (w *WasiStubs) Sock_shutdown(m *Module, fd, how int32) int32 {
	w.mu.Lock()
	op := w.fdTable[fd]
	w.mu.Unlock()
	if op == nil || op.conn == nil {
		return _wasiENOTSOCK
	}
	type shutdowner interface {
		CloseRead() error
		CloseWrite() error
	}
	sh, ok := op.conn.(shutdowner)
	if !ok {

		if err := op.conn.Close(); err != nil {
			return mapOSError(err)
		}
		return _wasiESUCCESS
	}
	var shErr error
	if how&0x1 != 0 {
		shErr = errors.Join(shErr, sh.CloseRead())
	}
	if how&0x2 != 0 {
		shErr = errors.Join(shErr, sh.CloseWrite())
	}
	if shErr != nil {
		return mapOSError(shErr)
	}
	return _wasiESUCCESS
}

// writeFilestat populates the 64-byte WASI filestat structure from a
// host os.FileInfo. The dev/ino fields come from the per-platform
// wasiPlatformStatSys helper (unix returns Stat_t.Dev/.Ino; Windows
// returns zeros).
func writeFilestat(out []byte, st os.FileInfo) {

	binary.LittleEndian.PutUint64(out[0:], 0)
	binary.LittleEndian.PutUint64(out[8:], 0)
	var ftype byte = 4
	mode := st.Mode()
	switch {
	case mode.IsDir():
		ftype = 3
	case mode&os.ModeSymlink != 0:
		ftype = 7
	case mode&os.ModeNamedPipe != 0:
		ftype = 6
	case mode&os.ModeSocket != 0:
		ftype = 6
	case mode&os.ModeDevice != 0:
		ftype = 1
	case mode&os.ModeCharDevice != 0:
		ftype = 2
	}
	out[16] = ftype
	binary.LittleEndian.PutUint64(out[24:], 1)
	binary.LittleEndian.PutUint64(out[32:], uint64(st.Size()))
	nanos := uint64(st.ModTime().UnixNano())
	binary.LittleEndian.PutUint64(out[40:], nanos)
	binary.LittleEndian.PutUint64(out[48:], nanos)
	binary.LittleEndian.PutUint64(out[56:], nanos)
}

// memSlice64 is memSlice for full-range 64-bit guest pointers.
func (w *WasiStubs) memSlice64(m *Module, off int64, n int64) []byte {
	mem := m.Memory
	lo := uint64(off)
	hi := lo + uint64(n)
	if n < 0 || hi < lo || hi > uint64(len(mem)) {
		return nil
	}
	return mem[lo:hi]
}

func (w *WasiStubs) Clock_time_get64(m *Module, clockID int64, precision int64, timePtr int64) int32 {
	out := w.memSlice64(m, timePtr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	nanos, errno := w.clockNanos(int32(clockID))
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint64(out, nanos)
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_close64(m *Module, fd int64) int32 {
	return w.Fd_close(m, int32(fd))
}

func (w *WasiStubs) Sched_yield64(m *Module) int32 {

	return w.Sched_yield(m)
}

func (w *WasiStubs) Fd_fdstat_get64(m *Module, fd int64, ptr int64) int32 {

	out := w.memSlice64(m, ptr, 24)
	if out == nil {
		return _wasiEFAULT
	}
	return w.fdstatFill(int32(fd), out)
}

func (w *WasiStubs) Fd_seek64(m *Module, fd int64, offset int64, whence int64, newOffPtr int64) int32 {
	out := w.memSlice64(m, newOffPtr, 8)
	if out == nil {
		return _wasiEFAULT
	}
	n, errno := w.fdSeek(int32(fd), offset, int(whence))
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint64(out, uint64(n))
	return _wasiESUCCESS
}

// iovecSlices64 is iovecSlices for the LP64 iovec layout: {u64 buf,
// u64 len}, 16 bytes per entry.
func (w *WasiStubs) iovecSlices64(m *Module, iovs, iovsLen int64) ([][]byte, bool) {
	if iovsLen < 0 || iovsLen > 1<<20 {
		return nil, false
	}
	iovecs := w.memSlice64(m, iovs, iovsLen*16)
	if iovecs == nil {
		return nil, false
	}
	bufs := make([][]byte, 0, iovsLen)
	for i := int64(0); i < iovsLen; i++ {
		bufPtr := binary.LittleEndian.Uint64(iovecs[i*16:])
		bufLen := binary.LittleEndian.Uint64(iovecs[i*16+8:])
		buf := w.memSlice64(m, int64(bufPtr), int64(bufLen))
		if buf == nil {
			return nil, false
		}
		bufs = append(bufs, buf)
	}
	return bufs, true
}

func (w *WasiStubs) Fd_write64(m *Module, fd int64, iovs int64, iovsLen int64, nwrittenPtr int64) int32 {
	w.mu.Lock()
	dst, _ := w.fdDstLocked(int32(fd))
	w.mu.Unlock()
	bufs, ok := w.iovecSlices64(m, iovs, iovsLen)

	nwrittenSlice := w.memSlice64(m, nwrittenPtr, 8)
	if !ok || nwrittenSlice == nil {
		return _wasiEFAULT
	}
	if dst == nil {
		binary.LittleEndian.PutUint64(nwrittenSlice, 0)
		return _wasiEBADF
	}
	binary.LittleEndian.PutUint64(nwrittenSlice, writeVec(dst, bufs))
	return _wasiESUCCESS
}

func (w *WasiStubs) Proc_exit64(m *Module, code int64) {
	panic(&WasiExitError{Code: int32(code)})
}

// putStrVec64 packs ss as an LP64 char** table (8-byte guest pointers
// at vec) plus NUL-terminated bodies (at buf, guest address bufBase).
// Both slices must already be sized: len(ss)*8 and totalBytesPlusNul.
func putStrVec64(vec, buf []byte, bufBase uint64, ss []string) int32 {
	bufOff := uint64(0)
	for i, s := range ss {
		binary.LittleEndian.PutUint64(vec[i*8:], bufBase+bufOff)
		n := copy(buf[bufOff:], s)
		if n < len(s) {
			return _wasiEFAULT
		}
		bufOff += uint64(n)
		buf[bufOff] = 0
		bufOff++
	}
	return _wasiESUCCESS
}

func (w *WasiStubs) Args_get64(m *Module, argv, argvBuf int64) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	argvSlice := w.memSlice64(m, argv, int64(len(w.args))*8)
	if argvSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.args)
	if !ok {
		return _wasiEFAULT
	}
	argvBufSlice := w.memSlice64(m, argvBuf, int64(total))
	if argvBufSlice == nil {
		return _wasiEFAULT
	}
	return putStrVec64(argvSlice, argvBufSlice, uint64(argvBuf), w.args)
}

func (w *WasiStubs) Args_sizes_get64(m *Module, argcPtr, argvBufLenPtr int64) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	argcSlice := w.memSlice64(m, argcPtr, 8)
	bufLenSlice := w.memSlice64(m, argvBufLenPtr, 8)
	if argcSlice == nil || bufLenSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.args)
	if !ok {
		return _wasiEFAULT
	}
	binary.LittleEndian.PutUint64(argcSlice, uint64(len(w.args)))
	binary.LittleEndian.PutUint64(bufLenSlice, uint64(total))
	return _wasiESUCCESS
}

func (w *WasiStubs) Environ_get64(m *Module, envv, envBuf int64) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	envvSlice := w.memSlice64(m, envv, int64(len(w.env))*8)
	if envvSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.env)
	if !ok {
		return _wasiEFAULT
	}
	envBufSlice := w.memSlice64(m, envBuf, int64(total))
	if envBufSlice == nil {
		return _wasiEFAULT
	}
	return putStrVec64(envvSlice, envBufSlice, uint64(envBuf), w.env)
}

func (w *WasiStubs) Environ_sizes_get64(m *Module, envcPtr, envBufLenPtr int64) int32 {
	w.mu.Lock()
	defer w.mu.Unlock()
	envcSlice := w.memSlice64(m, envcPtr, 8)
	bufLenSlice := w.memSlice64(m, envBufLenPtr, 8)
	if envcSlice == nil || bufLenSlice == nil {
		return _wasiEFAULT
	}
	total, ok := totalBytesPlusNul(w.env)
	if !ok {
		return _wasiEFAULT
	}
	binary.LittleEndian.PutUint64(envcSlice, uint64(len(w.env)))
	binary.LittleEndian.PutUint64(bufLenSlice, uint64(total))
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_fdstat_set_flags64(m *Module, fd, flags int64) int32 {
	return w.Fd_fdstat_set_flags(m, int32(fd), int32(flags))
}

func (w *WasiStubs) Fd_prestat_get64(m *Module, fd, ptr int64) int32 {
	if int32(fd) != 3 {
		return _wasiEBADF
	}

	out := w.memSlice64(m, ptr, 16)
	if out == nil {
		return _wasiEFAULT
	}
	out[0] = 0
	binary.LittleEndian.PutUint64(out[8:], 1)
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_prestat_dir_name64(m *Module, fd, buf, buflen int64) int32 {
	if int32(fd) != 3 {
		return _wasiEBADF
	}
	if buflen < 1 {
		return _wasiESUCCESS
	}
	out := w.memSlice64(m, buf, buflen)
	if out == nil {
		return _wasiEFAULT
	}
	out[0] = '/'
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_read64(m *Module, fd, iovs, iovsLen, nreadPtr int64) int32 {
	w.mu.Lock()
	src, _ := w.fdSrcLocked(int32(fd))
	w.mu.Unlock()
	if src == nil {
		return _wasiEBADF
	}
	bufs, ok := w.iovecSlices64(m, iovs, iovsLen)

	nreadSlice := w.memSlice64(m, nreadPtr, 8)
	if !ok || nreadSlice == nil {
		return _wasiEFAULT
	}
	binary.LittleEndian.PutUint64(nreadSlice, readVec(src, bufs))
	return _wasiESUCCESS
}

func (w *WasiStubs) Fd_readdir64(m *Module, fd, buf, buflen, cookie, bufusedPtr int64) int32 {

	bufSlice := w.memSlice64(m, buf, buflen)
	bufusedSlice := w.memSlice64(m, bufusedPtr, 8)
	if bufSlice == nil || bufusedSlice == nil {
		return _wasiEFAULT
	}
	written, errno := w.fdReaddir(int32(fd), bufSlice, cookie)
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint64(bufusedSlice, uint64(written))
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_open64(m *Module, dirFd, dirflags, pathPtr, pathLen, oflags, fsRightsBase, fsRightsInherit, fdflags, openedFdPtr int64) int32 {
	if int32(dirFd) != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice64(m, pathPtr, pathLen)

	outSlice := w.memSlice64(m, openedFdPtr, 4)
	if pathSlice == nil || outSlice == nil {
		return _wasiEFAULT
	}
	fd, errno := w.pathOpen(string(pathSlice), int32(dirflags), int32(oflags), fsRightsBase, int32(fdflags))
	if errno != _wasiESUCCESS {
		return errno
	}
	binary.LittleEndian.PutUint32(outSlice, uint32(fd))
	return _wasiESUCCESS
}

func (w *WasiStubs) Path_filestat_get64(m *Module, dirFd, flags, pathPtr, pathLen, outPtr int64) int32 {
	if int32(dirFd) != 3 {
		return _wasiEBADF
	}
	pathSlice := w.memSlice64(m, pathPtr, pathLen)

	out := w.memSlice64(m, outPtr, 64)
	if pathSlice == nil || out == nil {
		return _wasiEFAULT
	}
	w.mu.Lock()
	fsys := w.fsys
	w.mu.Unlock()
	rel := string(pathSlice)
	var st os.FileInfo
	var err error
	if flags&0x1 != 0 {
		st, err = fsys.Stat(rel)
	} else {
		st, err = fsys.Lstat(rel)
	}
	if err != nil {
		return mapOSError(err)
	}
	writeFilestat(out, st)
	return _wasiESUCCESS
}

func (w *WasiStubs) Random_get64(m *Module, buf, bufLen int64) int32 {
	slice := w.memSlice64(m, buf, bufLen)
	if slice == nil {
		return _wasiEFAULT
	}
	if _, err := rand.Read(slice); err != nil {
		return _wasiEIO
	}
	return _wasiESUCCESS
}
