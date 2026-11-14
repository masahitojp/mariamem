package main
import("go/ast";"go/parser";"go/token";"go/format";"os";"fmt";"strconv";"bytes")
func die(s string){panic(s)}
func lit(e ast.Expr)uint64{v,ok:=e.(*ast.BasicLit);if !ok||v.Kind!=token.INT{die("nonliteral offset/width")};n,err:=strconv.ParseUint(v.Value,0,64);if err!=nil{panic(err)};return n}
func call(e ast.Expr,name string)*ast.CallExpr{c,ok:=e.(*ast.CallExpr);if !ok{return nil};if id,ok:=c.Fun.(*ast.Ident);ok&&id.Name==name{return c};return nil}
func pure(e ast.Expr)bool{switch v:=e.(type){case *ast.Ident,*ast.BasicLit:return true;case *ast.ParenExpr:return pure(v.X);case *ast.BinaryExpr:return pure(v.X)&&pure(v.Y);case *ast.UnaryExpr:return v.Op!=token.ARROW&&pure(v.X);case *ast.CallExpr:if sel,ok:=v.Fun.(*ast.SelectorExpr);ok&&text(sel)=="base.Ui32"{return len(v.Args)==1&&pure(v.Args[0])};if id,ok:=v.Fun.(*ast.Ident);ok&&(id.Name=="uint32"||id.Name=="int32"||id.Name=="uint"||id.Name=="int"){return len(v.Args)==1&&pure(v.Args[0])}};return false}
func normalized(e ast.Expr)bool{if _,ok:=e.(*ast.BasicLit);ok{return lit(e)<=0xffffffff};c:=call(e,"uint64");if c==nil||len(c.Args)!=1{return false};d:=call(c.Args[0],"uint32");return d!=nil&&len(d.Args)==1&&pure(d.Args[0])}
func expr(s string)ast.Expr{e,err:=parser.ParseExpr(s);if err!=nil{panic(err)};return e}
func text(e ast.Node)string{var b bytes.Buffer;format.Node(&b,token.NewFileSet(),e);return b.String()}
func main(){if len(os.Args)!=4{die("input output function")};fs:=token.NewFileSet();f,err:=parser.ParseFile(fs,os.Args[1],nil,0);if err!=nil{panic(err)};target:=os.Args[3];count:=0;found:=false
for _,d:=range f.Decls{fn,ok:=d.(*ast.FuncDecl);if !ok||fn.Name.Name!=target{continue};found=true
ast.Inspect(fn,func(n ast.Node)bool{if id,ok:=n.(*ast.Ident);ok&&(id.Name=="mariamemBoundsTrap"||id.Name=="mariamemEA"){die("reserved name collision")};return true})
var rewrite func(*ast.BlockStmt)
rewrite=func(block *ast.BlockStmt){var result []ast.Stmt
for _,st:=range block.List{
// Recursively transform nested blocks first; only direct assignment statements are eligible.
ast.Inspect(st,func(n ast.Node)bool{if b,ok:=n.(*ast.BlockStmt);ok{rewrite(b);return false};return true})
a,ok:=st.(*ast.AssignStmt);if !ok{result=append(result,st);continue};var calls []*ast.CallExpr
ast.Inspect(a,func(n ast.Node)bool{c,ok:=n.(*ast.CallExpr);if !ok{return true};sel,ok:=c.Fun.(*ast.SelectorExpr);if ok&&text(sel)=="base.MemoryEA"{calls=append(calls,c)};return true})
if len(calls)==0{result=append(result,st);continue};if len(calls)!=1||len(a.Lhs)!=1||len(a.Rhs)!=1{die("unsupported assignment shape")}
c:=calls[0];if len(c.Args)!=4||text(c.Args[0])!="m"||!normalized(c.Args[1])||lit(c.Args[2])>0xffffffff{die("unproven memory32 address "+text(c))};width:=lit(c.Args[3]);if width!=1&&width!=2&&width!=4&&width!=8{die("unsupported width")}
ast.Inspect(a,func(n ast.Node)bool{cc,ok:=n.(*ast.CallExpr);if !ok{return true};switch fun:=cc.Fun.(type){case *ast.Ident:switch fun.Name{case "uint","int","uint64","uint32","int32","int64","uint8","int8","uint16","int16","float32","float64":default:die("effectful call "+fun.Name)};case *ast.SelectorExpr:if text(fun)!="base.MemoryEA"&&text(fun)!="unsafe.Add"&&text(fun)!="base.I64_extend_i32_u"&&text(fun)!="base.I64_rotl"&&text(fun)!="base.Ui32"{die("unknown selector call "+text(fun))};case *ast.ParenExpr:ptr,ok:=fun.X.(*ast.StarExpr);if !ok{die("non-type parenthesized call")};id,ok:=ptr.X.(*ast.Ident);if !ok{die("non-scalar pointer type")};switch id.Name{case "uint8","int8","uint16","int16","uint32","int32","uint64","int64","float32","float64":default:die("non-scalar pointer type")};default:die("unknown call shape")};return true})
ea:=&ast.AssignStmt{Lhs:[]ast.Expr{ast.NewIdent("mariamemEA")},Tok:token.DEFINE,Rhs:[]ast.Expr{&ast.BinaryExpr{X:&ast.CallExpr{Fun:ast.NewIdent("uint64"),Args:[]ast.Expr{c.Args[1]}},Op:token.ADD,Y:c.Args[2]}}}
condition:=expr(fmt.Sprintf("mariamemEA + %d > m.MemSize.Load()",width));check:=&ast.IfStmt{Cond:condition,Body:&ast.BlockStmt{List:[]ast.Stmt{&ast.BranchStmt{Tok:token.GOTO,Label:ast.NewIdent("mariamemBoundsTrap")}}}}
*c=ast.CallExpr{Fun:ast.NewIdent("uint64"),Args:[]ast.Expr{ast.NewIdent("mariamemEA")}}
result=append(result,&ast.BlockStmt{List:[]ast.Stmt{ea,check,a}});count++
};block.List=result}
rewrite(fn.Body);if count==0{die("no accesses")};old:=fn.Body;fn.Body=&ast.BlockStmt{List:[]ast.Stmt{old,&ast.LabeledStmt{Label:ast.NewIdent("mariamemBoundsTrap"),Stmt:&ast.ExprStmt{X:expr(`panic("wasm: memory access out of bounds")`)}}}}
ast.Inspect(fn,func(n ast.Node)bool{if c,ok:=n.(*ast.CallExpr);ok{if sel,ok:=c.Fun.(*ast.SelectorExpr);ok&&text(sel)=="base.MemoryEA"{die("unhandled MemoryEA location")}};return true})
}
if !found{die("target absent")};var buf bytes.Buffer;if err:=format.Node(&buf,fs,f);err!=nil{panic(err)};if err:=os.WriteFile(os.Args[2],buf.Bytes(),0600);err!=nil{panic(err)};fmt.Println(target,count)
}
