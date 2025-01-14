from typing import Any

import cmd2

from angr import Project, SimState, SimulationManager
from angrcli.plugins.ContextView.colors import Color, ColoredString


class GUICallbackBaseClass:
    def update_ip(self, ip: int) -> None:
        pass


class BinjaCallback(GUICallbackBaseClass):
    def __init__(self, bv: Any):
        self.bv = bv

    def update_ip(self, ip: int) -> None:
        self.bv.file.navigate(self.bv.file.view, ip)


class ExploreInteractive(cmd2.Cmd):

    intro: ColoredString = Color.redify("[!] Dropping into angr shell\n")
    intro += Color.redify(
        "Available Commands: print, (p)ick, (r)un, (s)tep, stepi, (q)uit"
    )  # type: ignore
    prompt: ColoredString = Color.redify(">>> ")

    def __init__(
        self,
        proj: Project,
        state: SimState,
        gui_callback_object: GUICallbackBaseClass = GUICallbackBaseClass(),
    ):
        super(ExploreInteractive, self).__init__(allow_cli_args=False)
        self.proj = proj
        self.simgr = proj.factory.simulation_manager(state)  # type: SimulationManager
        if "deferred" not in self.simgr.stashes:
            self.simgr.stashes["deferred"] = []
        self.gui_cb = gui_callback_object

    @property
    def state(self) -> SimState:
        """
        Alias to `self.simgr.one_active`
        :return:
        """
        return self.simgr.one_active

    def _clearScreen(self) -> None:
        print("\033[H\033[J")

    def do_quit(self, args: str) -> bool:
        """Quits the cli."""
        print(Color.redify("Exiting cmd-loop"))
        return True

    def do_q(self, args: str) -> bool:
        self.do_quit(args)
        return True

    def do_print(self, arg: str) -> None:
        """
        print [state_number]
        Prints a state
        state_number optionally specifies the state to print if multiple are available
        """
        if not arg:
            arg = "0"

        pick = int(arg)
        active = len(self.simgr.active)
        if pick >= active:
            print(
                Color.redify("Only {} active state(s), indexed from 0".format(active))
            )
        else:
            self.simgr.active[pick].context_view.pprint()
            self.gui_cb.update_ip(self.simgr.active[pick].addr)

    def do_stepi(self, args: str) -> None:
        """
        stepi
        Steps one instruction
        """
        if len(self.simgr.active) == 1:
            self.simgr.step(num_inst=1)
            self._clearScreen()
            if len(self.simgr.active) == 0:
                print(Color.redify("State terminated"))
                self._handle_state_termination()
            else:
                self.simgr.one_active.context_view.pprint(linear_code=True)
                self.gui_cb.update_ip(self.simgr.one_active.addr)
        elif len(self.simgr.active) > 1:
            for idx, state in enumerate(self.simgr.active):
                print(state.context_view._pstr_branch_info(idx))

    def do_step(self, args: str) -> None:
        """
        step
        Steps the current state one basic block
        """
        if len(self.simgr.active) == 1:
            self.simgr.step()
            self._clearScreen()
            if len(self.simgr.active) == 0:
                print(Color.redify("State terminated"))
                self._handle_state_termination()
            else:
                self.simgr.one_active.context_view.pprint()
                self.gui_cb.update_ip(self.simgr.one_active.addr)
        elif len(self.simgr.active) > 1:
            for idx, state in enumerate(self.simgr.active):
                print(state.context_view._pstr_branch_info(idx))

    def do_s(self, args: str) -> None:
        self.do_step(args)

    def do_run(self, args: str) -> None:
        """
        run [state_number]
        Runs until a branch is encountered
        state_number optionally picks a state if multiple are available
        """
        if len(self.simgr.active) > 1 and args:
            self.do_pick(args)
        if len(self.simgr.active) == 1:
            self.simgr.run(until=lambda s: len(s.active) != 1)
            if self.simgr.active:
                self.gui_cb.update_ip(self.simgr.one_active.addr)

        if len(self.simgr.active) > 0:
            for i, state in enumerate(self.simgr.active):
                print(state.context_view._pstr_branch_info(i))
        else:
            print(Color.redify("STATE FINISHED EXECUTION"))
            self._handle_state_termination()

    def do_r(self, args: str) -> None:
        self.do_run(args)

    def do_pick(self, arg: str) -> None:
        """
        pick <state_number>
        Selects a state to continue if multiple are available, the other state is saved
        """
        try:
            pick = int(arg)
            ip = self.simgr.active[pick].regs.ip
        except:
            print(
                "Invalid Choice: "
                + Color.redify("{}".format(arg))
                + ", for {}".format(self.simgr)
            )
            return
        print(Color.redify("Picking state with ip: " + (str(ip))))
        self.simgr.move(
            from_stash="active",
            to_stash="deferred",
            filter_func=lambda x: x.solver.eval(ip != x.regs.ip),
        )
        self.simgr.step()
        self._clearScreen()
        self.simgr.one_active.context_view.pprint()

    def do_hexdump(self, args: str):
        """
        hexdump <concrete_address>
        Show content of memory at the concrete_address
        """
        cmd_arg_list = args.arg_list
        address = int(cmd_arg_list[0],16)
        size = int(cmd_arg_list[1], 16)
        memory_hex = self.state.memory.hex_dump(address, size)
        mem_hex = ''.join(memory_hex)
        print(mem_hex)

    def do_history(self, args: str):
        """
        history
        Show parents of current state
        """
        #cmd_arg_list = args.arg_list
        #address = int(cmd_arg_list[0],16)
        #size = int(cmd_arg_list[1], 16)
        #memory_hex = self.state.memory.hex_dump(address, size)
        #mem_hex = ''.join(memory_hex)
        state_parents = self.state.history.parents
        the_history = ''
        for s in state_parents:
            try:
                the_history = the_history + hex(s.addr) + " -> "
            except Exception:
                pass
        print(the_history)
    
    def do_show_symbolic_vars(self, args: str):
        """
        symbolic_vars
        Providing that the StateOption 
        angr.options.REVERSE_MEMORY_NAME_MAP is enabled, 
        this shows the mapping between symbolic var names and where are 
        they in memory.
        """    
        if angr.options.REVERSE_MEMORY_NAME_MAP in self.state.options:
            for sym_var_name, mem_locs in self.state.memory.mem._name_mapping.items(): 
                mem_loc_hex = [hex(x) for x in mem_locs]
                print( Color.greenify("{}".format(sym_var_name)) + " | " + str(mem_loc_hex) )
        else:
            print("angr.options.REVERSE_MEMORY_NAME_MAP must be enabled to support this!")

    def do_show_constraints(self, args: str):
        """
        constraints
        Show constraints on current state
        """
        print(self.state.solver.constraints)

    
    def _do_set_byte(self, args:str):
        """
        change memory
        Set memory to specific value
        """
        cmd_arg_list = args.arg_list
        address = int(cmd_arg_list[0],16)
        value = int(cmd_arg_list[1], 16)
        if value < 0 or value > 0xff:
            print("Give me only a byte for now.")
        else:
            self.state.memory.store(address, value, 8 , endness='Iend_LE')


    def do_p(self, args: str) -> None:
        self.do_pick(args)

    def do_EOF(self, args: str) -> bool:
        self.do_quit(args)
        return True

    def do_hd(self, args: str) -> bool:
        self.do_hexdump(args)

    def do_hy(self, args: str) -> bool:
        self.do_history(args)

    def do_show_cst(self, args: str) -> bool:
        self.do_show_constraints(args)
    
    def do_show_sym_vars(self, args: str) -> bool:
        self.do_show_symbolic_vars(args)
    
    def do_set_byte(self, args: str) -> bool:
        self._do_set_byte(args)
        
    def _handle_state_termination(self) -> None:
        self.simgr.deadended[-1].context_view.pprint()
        if len(self.simgr.stashes["deferred"]) == 0:
            print(Color.redify("No states left to explore"))
        else:  # DFS-style like
            state = self.simgr.stashes["deferred"].pop()
            print(
                Color.redify("Other side of last branch with jumpguard ")
                + Color.greenify(str(state.solver.simplify(state.history.jump_guard)))
                + Color.redify(" has been added to {}".format(self.simgr))
            )
            self.simgr.stashes["active"].append(state)
