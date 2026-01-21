; ModuleID = 'bhumi'
source_filename = "main.bhumi"
@__argv_ptr = global i8** null
declare i8* @malloc(i64)
declare void @free(i8*)
declare i64 @strlen(i8*)
declare i32 @puts(i8*)
declare void @exit(i32)
declare i64 @time(i64*)
declare void @srand(i32)
declare i32 @rand()
declare i32 @usleep(i32)

@bhumi_argc_global = global i64 0
@bhumi_argv_global = global i8** null

define i64 @bhumi_argc() {
entry:
  %t0 = load i64, i64* @bhumi_argc_global
  ret i64 %t0
}

define i8* @bhumi_argv(i64 %idx) {
entry:
  %argvp = load i8**, i8*** @bhumi_argv_global
  %isnull = icmp eq i8** %argvp, null
  br i1 %isnull, label %null_case, label %check_bounds
null_case:
  %src = getelementptr inbounds [5 x i8], [5 x i8]* @.str_null, i32 0, i32 0
  %alloc0 = call i8* @bhumi_malloc(i64 5)
  call void @llvm.memcpy.p0i8.p0i8.i64(i8* %alloc0, i8* %src, i64 5, i1 false)
  ret i8* %alloc0
check_bounds:
  %argc = load i64, i64* @bhumi_argc_global
  %neg = icmp slt i64 %idx, 0
  %uge = icmp uge i64 %idx, %argc
  %oob = or i1 %neg, %uge
  br i1 %oob, label %null_case2, label %in_bounds
null_case2:
  %src2 = getelementptr inbounds [5 x i8], [5 x i8]* @.str_null, i32 0, i32 0
  %alloc1 = call i8* @bhumi_malloc(i64 5)
  call void @llvm.memcpy.p0i8.p0i8.i64(i8* %alloc1, i8* %src2, i64 5, i1 false)
  ret i8* %alloc1
in_bounds:
  %gep = getelementptr inbounds i8*, i8** %argvp, i64 %idx
  %val = load i8*, i8** %gep
  %len = call i64 @strlen(i8* %val)
  %allocsz = add i64 %len, 1
  %alloc2 = call i8* @bhumi_malloc(i64 %allocsz)
  call void @llvm.memcpy.p0i8.p0i8.i64(i8* %alloc2, i8* %val, i64 %allocsz, i1 false)
  ret i8* %alloc2
}

define void @user_main() {
entry:
  ret void
}
@.str_null = private unnamed_addr constant [5 x i8] c"null\00"

define i32 @main(i32 %argc, i8** %argv) {
entry:
  %argc64 = sext i32 %argc to i64
  store i64 %argc64, i64* @bhumi_argc_global
  store i8** %argv, i8*** @bhumi_argv_global
  call void @bhumi_init_runtime()
  call void @user_main()
  ret i32 0
}

@.oob_msg = private unnamed_addr constant [52 x i8] c"[BhumiCompiler-RT-CHCK]: Index out of bounds error.\00"
@.null_msg = private unnamed_addr constant [45 x i8] c"[BhumiCompiler-RT-CHCK]: Null pointer deref.\00"
@.heap_msg = private unnamed_addr constant [67 x i8] c"[BhumiCompiler-RT-HEAP]: Invalid free or heap corruption detected.\00"
@.alloc_magic = global i64 0
define void @bhumi_oob_abort() {
entry:
  %tmp_puts = call i32 @puts(i8* getelementptr inbounds ([52 x i8], [52 x i8]* @.oob_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define void @bhumi_null_abort() {
entry:
  %tmp_puts1 = call i32 @puts(i8* getelementptr inbounds ([45 x i8], [45 x i8]* @.null_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define void @bhumi_init_runtime() {
entry:
  %t = call i64 @time(i64* null)
  %t32 = trunc i64 %t to i32
  call void @srand(i32 %t32)
  %r = call i32 @rand()
  %r64 = zext i32 %r to i64
  %xor_magic = xor i64 %r64, 16045690984833335023
  store i64 %xor_magic, i64* @.alloc_magic
  ret void
}
define i8* @bhumi_malloc(i64 %usize) {
entry:
  %hdr_sz = add i64 %usize, 24
  %ovf = icmp ult i64 %hdr_sz, %usize
  br i1 %ovf, label %oom, label %try_malloc
oom:
  %tmp_puts_oom = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
try_malloc:
  %raw = call i8* @malloc(i64 %hdr_sz)
  %isnull = icmp eq i8* %raw, null
  br i1 %isnull, label %oom_malloc, label %ok_alloc
oom_malloc:
  %tmp_puts_oom2 = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
ok_alloc:
  %hdr_ptr = bitcast i8* %raw to i64*
  %global_magic = load i64, i64* @.alloc_magic
  store i64 %global_magic, i64* %hdr_ptr
  %size_slot = getelementptr i8, i8* %raw, i64 8
  %size_slot_i64 = bitcast i8* %size_slot to i64*
  store i64 %usize, i64* %size_slot_i64
  %user_ptr = getelementptr i8, i8* %raw, i64 16
  %footer_ptr = getelementptr i8, i8* %user_ptr, i64 %usize
  %footer_ptr_i64 = bitcast i8* %footer_ptr to i64*
  store i64 %global_magic, i64* %footer_ptr_i64
  ret i8* %user_ptr
}
define void @bhumi_free(i8* %userptr) {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %ret_void, label %check_hdr
check_hdr:
  %raw_hdr = getelementptr i8, i8* %userptr, i64 -16
  %hdr_i64 = bitcast i8* %raw_hdr to i64*
  %magic = load i64, i64* %hdr_i64
  %global_magic_cmp = load i64, i64* @.alloc_magic
  %ok = icmp eq i64 %magic, %global_magic_cmp
  br i1 %ok, label %free_ok, label %free_fail
free_fail:
  %tmp_puts2 = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
free_ok:
  %size_slot = getelementptr i8, i8* %raw_hdr, i64 8
  %size_i64 = bitcast i8* %size_slot to i64*
  %sz = load i64, i64* %size_i64
  %footer_loc = getelementptr i8, i8* %userptr, i64 %sz
  %footer_i64 = bitcast i8* %footer_loc to i64*
  %footer_val = load i64, i64* %footer_i64
  %ok2 = icmp eq i64 %footer_val, %global_magic_cmp
  br i1 %ok2, label %free_ok2, label %free_fail2
free_fail2:
  %tmp_puts3 = call i32 @puts(i8* getelementptr inbounds ([67 x i8], [67 x i8]* @.heap_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
free_ok2:
  store i64 0, i64* %hdr_i64
  %rawptr = bitcast i8* %raw_hdr to i8*
  call void @free(i8* %rawptr)
  ret void
ret_void:
  ret void
}
@.vvolatile_msg = private unnamed_addr constant [69 x i8] c"[BhumiCompiler-RT-CHCK]: Volatile write attempted in vasync (panic).\00"
define void @bhumi_vvolatile_abort() {
entry:
  %tmp_puts_vv = call i32 @puts(i8* getelementptr inbounds ([69 x i8], [69 x i8]* @.vvolatile_msg, i32 0, i32 0))
  call void @exit(i32 1)
  unreachable
}
define i64 @bhumi_alloc_size(i8* %userptr) {
entry:
  %is_null = icmp eq i8* %userptr, null
  br i1 %is_null, label %ret_zero, label %cont
cont:
  %raw_hdr = getelementptr i8, i8* %userptr, i64 -16
  %hdr_i64 = bitcast i8* %raw_hdr to i64*
  %magic = load i64, i64* %hdr_i64
  %global_magic_cmp = load i64, i64* @.alloc_magic
  %ok = icmp eq i64 %magic, %global_magic_cmp
  br i1 %ok, label %ok2, label %ret_zero
ok2:
  %size_slot = getelementptr i8, i8* %raw_hdr, i64 8
  %size_i64 = bitcast i8* %size_slot to i64*
  %sz = load i64, i64* %size_i64
  ret i64 %sz
ret_zero:
  ret i64 0
}
%bhumi_node = type { i8*, i8*, %bhumi_node* }
@bhumi_buckets = global [1024 x %bhumi_node*] zeroinitializer
define void @bhumi_register_async(i8* %resume, i8* %handle) {
entry:
  %szptr = getelementptr %bhumi_node, %bhumi_node* null, i32 1
  %sz = ptrtoint %bhumi_node* %szptr to i64
  %raw = call i8* @malloc(i64 %sz)
  %node = bitcast i8* %raw to %bhumi_node*
  %rptr = getelementptr %bhumi_node, %bhumi_node* %node, i32 0, i32 0
  %hptr = getelementptr %bhumi_node, %bhumi_node* %node, i32 0, i32 1
  %nptr = getelementptr %bhumi_node, %bhumi_node* %node, i32 0, i32 2
  store i8* %resume, i8** %rptr
  store i8* %handle, i8** %hptr
  %h_addr = ptrtoint i8* %handle to i64
  %bucket_idx64 = and i64 %h_addr, 1023
  %bucket_idx = trunc i64 %bucket_idx64 to i32
  %slot = getelementptr [1024 x %bhumi_node*], [1024 x %bhumi_node*]* @bhumi_buckets, i32 0, i32 %bucket_idx
  br label %insert_loop
insert_loop:
  %old_head = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  store %bhumi_node* %old_head, %bhumi_node** %nptr
  %pair = cmpxchg %bhumi_node** %slot, %bhumi_node* %old_head, %bhumi_node* %node seq_cst seq_cst
  %succ = extractvalue { %bhumi_node*, i1 } %pair, 1
  br i1 %succ, label %insert_done, label %insert_loop
insert_done:
  ret void
}
define void @bhumi_remove_and_free_node(%bhumi_node* %target, %bhumi_node** %slot) {
entry:
  br label %try_head
try_head:
  %head = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  %is_head = icmp eq %bhumi_node* %head, %target
  br i1 %is_head, label %remove_head, label %scan_pred
remove_head:
  %t_nptr = getelementptr %bhumi_node, %bhumi_node* %target, i32 0, i32 2
  %t_next = load atomic %bhumi_node*, %bhumi_node** %t_nptr seq_cst, align 8
  %pair = cmpxchg %bhumi_node** %slot, %bhumi_node* %target, %bhumi_node* %t_next seq_cst seq_cst
  %succ = extractvalue { %bhumi_node*, i1 } %pair, 1
  br i1 %succ, label %freed, label %try_head
scan_pred:
  %pred0 = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  br label %scan_loop
scan_loop:
  %pred = phi %bhumi_node* [ %pred0, %scan_pred ], [ %pred_next, %advance_pred ]
  %pred_is_null = icmp eq %bhumi_node* %pred, null
  br i1 %pred_is_null, label %notfound, label %check_pred_next
check_pred_next:
  %pred_nptr = getelementptr %bhumi_node, %bhumi_node* %pred, i32 0, i32 2
  %pred_next = load atomic %bhumi_node*, %bhumi_node** %pred_nptr seq_cst, align 8
  %cmp_pred = icmp eq %bhumi_node* %pred_next, %target
  br i1 %cmp_pred, label %try_remove_mid, label %advance_pred
try_remove_mid:
  %target_nptr = getelementptr %bhumi_node, %bhumi_node* %target, i32 0, i32 2
  %target_next = load atomic %bhumi_node*, %bhumi_node** %target_nptr seq_cst, align 8
  %pair2 = cmpxchg %bhumi_node** %pred_nptr, %bhumi_node* %target, %bhumi_node* %target_next seq_cst seq_cst
  %succ2 = extractvalue { %bhumi_node*, i1 } %pair2, 1
  br i1 %succ2, label %freed, label %scan_pred
advance_pred:
  br label %scan_loop
notfound:
  ret void
freed:
  %rawptr = bitcast %bhumi_node* %target to i8*
  call void @free(i8* %rawptr)
  ret void
}
define void @bhumi_block_until_complete(i8* %handle) {
entry:
  %h_addr = ptrtoint i8* %handle to i64
  %bucket_idx64 = and i64 %h_addr, 1023
  %bucket_idx = trunc i64 %bucket_idx64 to i32
  %slot = getelementptr [1024 x %bhumi_node*], [1024 x %bhumi_node*]* @bhumi_buckets, i32 0, i32 %bucket_idx
  br label %scan
scan:
  %head = load atomic %bhumi_node*, %bhumi_node** %slot seq_cst, align 8
  br label %scan_loop
scan_loop:
  %cur = phi %bhumi_node* [ %head, %scan ], [ %next, %advance ]
  %isnull = icmp eq %bhumi_node* %cur, null
  br i1 %isnull, label %sleep, label %checknode
checknode:
  %hptr = getelementptr %bhumi_node, %bhumi_node* %cur, i32 0, i32 1
  %hval = load atomic i8*, i8** %hptr seq_cst, align 8
  %cmp = icmp eq i8* %hval, %handle
  br i1 %cmp, label %invoke, label %advance
invoke:
  %rptr = getelementptr %bhumi_node, %bhumi_node* %cur, i32 0, i32 0
  %rval = load atomic i8*, i8** %rptr seq_cst, align 8
  %resume_fn = bitcast i8* %rval to i1 (i8*)*
  %res = call i1 %resume_fn(i8* %handle)
  br i1 %res, label %remove_node, label %scan
remove_node:
  call void @bhumi_remove_and_free_node(%bhumi_node* %cur, %bhumi_node** %slot)
  br label %done
advance:
  %nptr2 = getelementptr %bhumi_node, %bhumi_node* %cur, i32 0, i32 2
  %next = load atomic %bhumi_node*, %bhumi_node** %nptr2 seq_cst, align 8
  br label %scan_loop
sleep:
  %tmp_usleep = call i32 @usleep(i32 1000)
  br label %scan
done:
  ret void
}
	