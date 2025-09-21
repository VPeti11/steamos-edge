# common utilities for the os-repair backends

# SPDX-License-Identifier: GPL-2.0+

# Copyright © 2022 Collabora Ltd
# Copyright © 2022 Valve Corporation

set -u
shopt -s extglob

declare prefix="/usr"
declare -r VERSION="0.02"
unset prefix
declare -r OS_REPAIR_LOGS=/tmp/steamos-reset/logs
declare -r OS_REPAIR_DATA=/tmp/steamos-reset/data
declare -l UUID=
declare -i LOG_NUMBER=0
declare DATA_FD=
declare DATA_TMPFILE=
declare -a TRAPS=()
declare -r FACTORY_RESET_CONFIG_DIR=/esp/efi/steamos/factory-reset

for dir in $OS_REPAIR_LOGS $OS_REPAIR_DATA
do
    [ -d $dir ] && continue
    mkdir -p $dir && chmod 1777 $dir
done

superuser ()
{
    [ ${EUID:-0} -eq 0 ]
}

quote_escape ()
{
    echo ${1//\"/\\\"}
}

uuid_ok ()
{
    case ${1:-$UUID} in
        (+([0-9a-f])-+([0-9a-f])-+([0-9a-f])-+([0-9a-f])-+([0-9a-f]))
            true
            ;;
        (*)
            false
            ;;
    esac
}

setup_session_dirs ()
{
    local uuid=${1:-$UUID}
    local sdir=

    uuid_ok "$uuid" || return 1

    for sdir in ${OS_REPAIR_DATA} ${OS_REPAIR_DATA}/${uuid} \
                ${OS_REPAIR_LOGS} ${OS_REPAIR_LOGS}/${uuid}
    do
        [ -d $sdir ] || mkdir -p $sdir
        superuser || continue
        chown http:http $sdir
        chmod ug+s,ug+rwx $sdir
    done
}

set_uuid ()
{
    uuid_ok || UUID=${1:-$(uuidgen)}
}

log_msg ()
{
    set_uuid
    uuid_ok || return 1
    setup_session_dirs

    local logs=${OS_REPAIR_LOGS}/${UUID}
    local file=${logs}/$(printf "%05d.log" $LOG_NUMBER)
    local errs=${logs}/error.log
    LOG_NUMBER=$((LOG_NUMBER + 1))

    # NOTE: this stderr capture is initiated by close_stdio
    # transcribe any stderr output so far:
    if [ -s $errs ] && cat $errs | sed -re 's/[\x00-\x08]//g; s/\r/\\r/g' >> $file
    then
        echo -n > "$errs"
    fi
    echo "$@" | sed -re 's/[\x00-\x08]//g' >> $file
    chmod 0644 "$file"
}

get_log_messages ()
{
    local -i first=${1:-0}
    local -i max=${2:-0}
    local -r uuid=${3:-${UUID}}
    local filter="-n"

    uuid_ok $uuid || return 1

    if [ $first -lt 0 ]
    then
        filter="-rn"
        first=$((first * -1 -1))
    fi
    
    (local -i nth=0
     local -i mth=0
     cd ${OS_REPAIR_LOGS}/${uuid} &&
     while read log
     do
         [ $((nth++)) -lt $first ] && continue
         [ $max -gt 0 ] && [ $((mth++)) -ge $max ] && break
         cat $log
     done < <(ls -1 *.log 2>/dev/null | sort $filter | grep -v error.log))
}

get_error_messages ()
{
    local -r uuid=${1:-${UUID}}
    cat ${OS_REPAIR_LOGS}/${uuid}/error.log
}

save_data ()
{
    local name=${1:-}
    local type=${2:-}

    uuid_ok || return 1
    setup_session_dirs

    local data=${OS_REPAIR_DATA}/${UUID}
    local file=$data/${name//[^A-Za-z0-9.-]/_}.${type//[^0-9A-Za-z.]/}
    local tmpf=$(mktemp $file.XXXXXXX)

    echo "${@:3}" > ${tmpf}
    superuser && chown http:http $tmpf
    chmod 0644 $tmpf
    mv "${tmpf}" "$file"
}

append_data ()
{
    local name=${1:-}
    local type=${2:-}

    uuid_ok || return 1
    setup_session_dirs

    local data=${OS_REPAIR_DATA}/${UUID}
    local file=$data/${name//[^A-Za-z0-9.-]/_}.${type//[^0-9A-Za-z.]/}
    local tmpf=$(mktemp $file.XXXXXXX)

    if [ -f $file ]
    then
        cat $file > $tmpf
    fi

    echo "${@:3}" >> $tmpf
    chown http:http $tmpf
    chmod 0644 $tmpf
    mv "${tmpf}" "$file"
}

get_data ()
{
    local name=${1:-}
    local type=${2:-}
    local uuid=${3:-$UUID}

    uuid_ok "$uuid" || return 1
    local data=${OS_REPAIR_DATA}/${uuid}
    local file=$data/${name//[^A-Za-z0-9.-]/_}.${type//[^0-9A-Za-z.]/}
    
    cat $file 2>/dev/null
}

del_data ()
{
    local name=${1:-}
    local type=${2:-}
    local uuid=${3:-$UUID}

    uuid_ok "$uuid" || return 1
    local data=${OS_REPAIR_DATA}/${uuid}
    local file=$data/${name//[^A-Za-z0-9.-]/_}.${type//[^0-9A-Za-z.]/}

    [ -f $file ] && rm -f $file 2>/dev/null
}

get_escaped ()
{
    local str=$(get_data "$@")
    quote_escape "$str"
}

set_session_type ()
{
    uuid_ok || return 1
    save_data session-type txt "$(basename $0)"
}

set_session_status ()
{
    local -i status=${1:-0}
    uuid_ok || return 1
    save_data session-status txt $status
}

get_session_type ()
{
    get_data session-type txt ${1:-}
}

get_session_status ()
{
    local -i status=0
    status=$(get_data session-status txt ${1:-})
    echo $status
}

list_sessions ()
{
    (cd ${OS_REPAIR_DATA} && ls -1 2>/dev/null)
}

list_data_by_type ()
{
    local type=${1:-data}
    local uuid=${2:-$UUID}
    local var=

    (cd ${OS_REPAIR_DATA}/${uuid};
     while read var
     do
         echo ${var%.$type}
     done  < <(ls -1 *.$type 2>/dev/null | grep -v "^*"))
}

close_data_fd ()
{
    local type=${1:-data}
    local to=${DATA_TMPFILE%.*}.${type//[^0-9A-Za-z.]/}

    if [ "$DATA_TMPFILE" ] && [ -f "$DATA_TMPFILE" ]
    then  
        if mv ${DATA_TMPFILE} ${to}
        then
            DATA_TMPFILE=
        fi
    fi

    if [ ${DATA_FD:-0} -gt 0 ]
    then
        exec {DATA_FD}>&-
        DATA_FD=
    fi
}

open_data_fd ()
{
    local name=${1:-default}
    local uuid=${2:-$UUID}

    name=${name//[^A-Za-z0-9.-]/_}
    
    uuid_ok "$uuid" || return 1
    setup_session_dirs $uuid

    close_data_fd
    
    local data=${OS_REPAIR_DATA}/${uuid}
    DATA_TMPFILE=$(mktemp ${data}/$name.XXXXXX)

    exec {DATA_FD}<>$DATA_TMPFILE
}

write_data_stream_fd ()
{
    if [ ${DATA_FD:-0} -gt 0 ]
    then
        cat - >&${DATA_FD}
    fi
}

write_data_fd ()
{
    if [ ${DATA_FD:-0} -gt 0 ]
    then
        echo -n "$@">&${DATA_FD}
    else
        echo write_data_fd called with no data fd open >&2
        return 1
    fi
}

save_json ()
{
    save_data "${1:-}" json "${@:2}"
}

file_ident ()
{
    [ -e "${1:-}" ] || echo "0.0";
    stat -c "%d.%i" $1
}

file_signature ()
{
    local file=${1:-}
    local sum=
    local -i size=0
    local x=

    if [ ! -e "$file" ]
    then
        echo 00000000-0000-0000-0000-000000000000.0
    else
        read sum x < <(sha256sum "$file")
        size=$(stat -c %s "$file")
        echo "$sum.$size"
    fi
}

clear_data ()
{
    local uuid=${1:-$UUID}
    local udir="$OS_REPAIR_DATA/$uuid"
    local topd_id=$(file_ident "$OS_REPAIR_DATA")
    local udir_id=
    local udirp_id=

    if [ -d "$udir" ]
    then
        udir_id=$(file_ident "$udir")
        udirp_id=$(file_ident "$udir/..")
        if [ "$udir_id" != "$topd_id" ] && [ "$udirp_id" = "$topd_id" ]
        then
            rm -rf "$udir"
        fi
    fi
}

clear_logs ()
{
    local uuid=${1:-$UUID}
    local udir="$OS_REPAIR_LOGS/$uuid"
    local topd_id=$(file_ident "$OS_REPAIR_LOGS")
    local udir_id=
    local udirp_id=

    if [ -d "$udir" ]
    then
        udir_id=$(file_ident "$udir")
        udirp_id=$(file_ident "$udir/..")
        if [ "$udir_id" != "$topd_id" ] && [ "$udirp_id" = "$topd_id" ]
        then
            rm -rf "$udir"
        fi
    fi
}

clear_session ()
{
    local uuid=${1:-$UUID}

    clear_data "$uuid"
    clear_logs "$uuid"
}

emit_json_header ()
{
    # empty query or one with content => we're in CGI mode
    if [ -n "${QUERY_STRING:-}" ] || [ -n "${QUERY_STRING+x}" ]
    then
        echo -ne "Content-Type: application/json\r\n\r\n"
    fi
}

close_stdio ()
{
    uuid_ok || return 1

    exec  >&-
    exec  <&-

    # redirect stderr to <SESSION-LOG-DIR>/error.log
    # log_msg will pick up any errors there and
    # include them in the session log
    local file=${OS_REPAIR_LOGS}/${UUID}/error.log
    exec 2>$file
}

emit_json_response ()
{
    local -r service=$(quote_escape $(basename "$0"))
    local -i status=${1:-102}
    local -r msg=$(quote_escape "${2:-}")

    emit_json_header

    if uuid_ok
    then
       cat - <<EOF
{"service": "$service",
 "version": "$VERSION",
 "status": $status,
 "message": "$msg",
 "uuid":"$UUID"}
EOF
    else
       cat - <<EOF
{"service": "$service",
 "version": "$VERSION",
 "status": $status,
 "message": "$msg"}
EOF
    fi
}

atomic_copy ()
{
    local src=${1:-}
    local dst=${2:-}
    local ext=$(basename $(mktemp -u XXXXXX))
    local rc=0

    [ -e "$src" ] || return 2

    local dir=$(dirname "$dst")

    if mkdir -p "$dir"       &&
       cp "$src" "$dst.$ext" &&
       mv "$dst.$ext" "$dst"
    then
        return 0
    else
        rc=$?
        rm -f "$dst.$ext"
        return ${rc:-1}
    fi
}

atomic_sync ()
{
    local src=${1:-}
    local dst=${2:-}

    local src_sig=$(file_signature "$src")
    local dst_sig=$(file_signature "$dst")

    if [ "$src_sig" = "$dst_sig" ]
    then
        return 0
    fi

    atomic_copy "$@"
}

apply_traps ()
{
    local trap_cmd=
    local cmd=
    local count=${#TRAPS[@]}

    trap - EXIT
    if [ $count -gt 0 ]
    then
        for cmd in "${TRAPS[@]}"
        do
            trap_cmd=${trap_cmd}${trap_cmd:+"; "}${cmd}
        done

        trap "$trap_cmd" EXIT
    fi
}

push_exit_trap ()
{
    TRAPS+=("${1:-echo -n}")
    apply_traps
}

pop_exit_trap ()
{
    unset TRAPS[-1]
    apply_traps
}

register_session_pid ()
{
    uuid_ok || return 1
    local pidfile=${OS_REPAIR_DATA}/${UUID}/session.pid
    push_exit_trap "rm -f $pidfile"
    save_data session pid $$
}

get_session_pid ()
{
    local uuid=${1:-$UUID}

    uuid_ok ${uuid} || return 1
    local -i spid=0
    spid=$(get_data session pid $uuid)
    echo $spid
}
