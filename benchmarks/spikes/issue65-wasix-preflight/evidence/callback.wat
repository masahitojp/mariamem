 (func $probe_callback (param $0 i32) (param $1 i32) (result i32)
  (call_indirect $0 (type $2)
   (i32.load
    (local.get $0)
   )
   (local.get $1)
   (i32.const 1)
   (i32.load offset=4
    (local.get $0)
   )
  )
 )
